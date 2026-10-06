"""Desarrollo: cachés de npm/pip/go/cargo/etc. y carpetas node_modules / venv olvidadas."""

from __future__ import annotations

import os
import time
from pathlib import Path

from ..contexto import Contexto
from ..modelo import Hallazgo, Item, Limpieza, Modo, Nivel, items_ordenados
from ..i18n import tr

MINIMO = 20 * 1024**2
DIAS_OLVIDADO = 30

# (ruta relativa al home, nombre, comando oficial equivalente: solo como referencia)
CACHES = [
    (".npm/_cacache", "npm", "npm cache clean --force"),
    (".cache/yarn", "yarn", "yarn cache clean"),
    (".cache/pnpm", "pnpm", "pnpm store prune"),
    (".local/share/pnpm/store", tr("pnpm (store)"), "pnpm store prune"),
    (".bun/install/cache", "bun", "bun pm cache rm"),
    (".cache/pip", "pip", "pip cache purge"),
    (".cache/uv", "uv", "uv cache clean"),
    (".cache/go-build", tr("go (compilación)"), "go clean -cache"),
    ("go/pkg/mod", tr("go (módulos)"), "go clean -modcache"),
    (".cargo/registry/cache", "cargo", "borrar ~/.cargo/registry/cache"),
    (".gradle/caches", "gradle", "borrar ~/.gradle/caches"),
    (".m2/repository", "maven", "borrar ~/.m2/repository"),
]


def detectar(ctx: Contexto) -> list[Hallazgo]:
    res: list[Hallazgo] = []
    detalle, rutas = [], []
    for rel, nombre, comando in CACHES:
        d = ctx.home / rel
        if not d.is_dir():
            continue
        peso, _ = ctx.medir(d)
        ctx.reclamar(d)
        if peso and peso >= MINIMO:
            detalle.append(Item(nombre, peso, d))
            rutas.append(d)
    if detalle:
        res.append(Hallazgo(
            tr("Desarrollo"), tr("Cachés de herramientas de programación"), Nivel.SEGURO,
            sum(i.peso or 0 for i in detalle),
            tr("Paquetes descargados por npm, pip, go, etc. Se vuelven a bajar solos cuando los necesitás "
              "(la próxima instalación tarda un poco más)."),
            rutas=rutas, detalle=items_ordenados(detalle),
            limpieza=Limpieza(Modo.BORRAR, por_item=True),
        ))
    res += _proyectos_olvidados(ctx)
    return res


def _proyectos_olvidados(ctx: Contexto) -> list[Hallazgo]:
    """node_modules y entornos virtuales de Python dentro del home (usa el escaneo si lo hay)."""
    home = str(ctx.home)
    esc = next((e for e in ctx.escaneos if e.raiz == os.path.realpath(home)), None)
    if esc is None:
        return []
    candidatos = []
    for d in esc.total:
        nombre = os.path.basename(d)
        es_node = nombre == "node_modules" and "/node_modules/" not in d[: -len(nombre)]
        es_venv = nombre in (".venv", "venv", "env") and os.path.isfile(os.path.join(d, "pyvenv.cfg"))
        if (es_node or es_venv) and "/." not in d[len(home):].replace("/.venv", ""):
            candidatos.append(d)

    ahora = time.time()
    detalle, rutas = [], []
    for d in candidatos:
        peso = esc.total[d]
        if peso < MINIMO:
            continue
        proyecto = os.path.dirname(d)
        dias = int((ahora - _ultima_modificacion(proyecto)) / 86400)
        marca = tr("sin tocar hace {n} días", n=dias) if dias >= DIAS_OLVIDADO else tr("proyecto activo")
        detalle.append(Item(f"{proyecto.replace(home, '~')}/{os.path.basename(d)}  ({marca})", peso, Path(d)))
        rutas.append(Path(d))
        ctx.reclamar(d)
    if not detalle:
        return []
    return [Hallazgo(
        tr("Desarrollo"), tr("Dependencias de proyectos (node_modules / venv)"), Nivel.REVISAR,
        sum(i.peso or 0 for i in detalle),
        tr("Librerías instaladas por proyecto. Se regeneran con `npm install` o `pip install -r ...`. "
          "Las de proyectos que no tocás hace rato son buenas candidatas."),
        rutas=rutas, detalle=items_ordenados(detalle),
        limpieza=Limpieza(Modo.PAPELERA, por_item=True),
    )]


def _ultima_modificacion(proyecto: str) -> float:
    """Fecha del archivo más reciente del proyecto, sin entrar en node_modules ni carpetas ocultas."""
    ultima = 0.0
    for raiz, dirs, archivos in os.walk(proyecto):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "venv", ".venv", "env") and not d.startswith(".")]
        for a in archivos:
            try:
                ultima = max(ultima, os.lstat(os.path.join(raiz, a)).st_mtime)
            except OSError:
                pass
    return ultima
