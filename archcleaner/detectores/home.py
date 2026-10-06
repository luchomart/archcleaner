"""Home: ~/.cache, papeleras, descargas viejas y posibles restos de programas desinstalados.

Corre al final: lo que ya reportó otro detector (ej. la caché de yay) no se cuenta dos veces.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from ..contexto import Contexto
from ..modelo import Hallazgo, Item, Limpieza, Modo, Nivel, items_ordenados
from ..util import dentro_de, ejecutar
from ..i18n import tr

MINIMO = 10 * 1024**2
MINIMO_RESTO = 20 * 1024**2
DIAS_DESCARGA_VIEJA = 90

# Carpetas genéricas de escritorio/KDE que no son de un programa puntual.
GENERICAS = {
    "autostart", "systemd", "fontconfig", "pulse", "dconf", "menus", "mime", "applications",
    "icons", "fonts", "keyrings", "sounds", "themes", "colorschemes", "trash", "recentdocuments",
    "xdgdesktopportal", "environment.d", "user-dirs.dirs", "gtk20", "gtk30", "gtk40",
    "kxmlgui5", "knotifications6", "kio", "plasmasystemmonitor", "konsole", "baloo",
    "kactivitymanagerd", "kscreen", "kwalletd", "plasma", "ksycoca", "ibus", "nvim",
}


def detectar(ctx: Contexto) -> list[Hallazgo]:
    res: list[Hallazgo] = []
    res += _cache(ctx)
    res += _papeleras(ctx)
    res += _descargas_viejas(ctx)
    res += _restos(ctx)
    return res


def _reclamada(ctx: Contexto, ruta: str) -> bool:
    return any(dentro_de(ruta, r) for r in ctx.reclamadas)


# Cachés que se regeneran, pero a un costo alto (gigas que se vuelven a bajar, o cosas que dejan
# de andar hasta reinstalarlas): van aparte y sin tildar.
CACHES_CARAS = {
    "huggingface": tr("modelos de IA descargados (pueden ser varios GB)"),
    "torch": tr("modelos de PyTorch descargados"),
    "whisper": tr("modelos de Whisper descargados"),
    "ms-playwright": tr("navegadores que instaló Playwright"),
    "pypoetry": tr("incluye los entornos virtuales de tus proyectos de Poetry"),
    "jetbrains": tr("índices de los IDE de JetBrains (reindexar tarda)"),
    "lm-studio": tr("modelos de LM Studio"),
}


def _cache(ctx: Contexto) -> list[Hallazgo]:
    cache = ctx.home / ".cache"
    if not cache.is_dir():
        return []
    detalle, rutas, caras = [], [], []
    for d in sorted(cache.iterdir()):
        if _reclamada(ctx, os.path.realpath(d)):
            continue
        peso, _ = ctx.medir(d)
        if not peso or peso < MINIMO:
            continue
        if motivo := CACHES_CARAS.get(d.name.lower()):
            caras.append(Item(f"{d.name}  ({motivo})", peso, d))
            continue
        detalle.append(Item(d.name, peso, d))
        rutas.append(d)
    if not detalle and not caras:
        return []
    ctx.reclamar(cache)
    res = []
    if caras:
        res.append(Hallazgo(
            tr("Home"), tr("Cachés que cuesta regenerar (~/.cache)"), Nivel.REVISAR, sum(i.peso or 0 for i in caras),
            tr("Técnicamente son caché, pero volver a tenerlas cuesta: descargas grandes o cosas que dejan "
              "de andar hasta reinstalarlas. Borralas solo si sabés que no las vas a usar."),
            rutas=[i.ruta for i in caras if i.ruta], detalle=items_ordenados(caras),
            limpieza=Limpieza(Modo.PAPELERA, por_item=True),
        ))
    if not detalle:
        return res
    return res + [Hallazgo(
        tr("Home"), tr("Caché de programas (~/.cache)"), Nivel.SEGURO, sum(i.peso or 0 for i in detalle),
        tr("Archivos temporales que los programas regeneran solos (miniaturas, caché del navegador, etc.). "
          "Conviene cerrar los programas antes de limpiar. Lo único que notás es que la primera vez "
          "algunas cosas cargan un poco más lento."),
        rutas=rutas, detalle=items_ordenados(detalle),
        limpieza=Limpieza(Modo.BORRAR, por_item=True,
                          nota=tr("Cerrá el navegador y los programas cuya caché vayas a borrar.")),
    )]


def _papeleras(ctx: Contexto) -> list[Hallazgo]:
    candidatas = [ctx.home / ".local/share/Trash"]
    uid = os.getuid()
    for linea in (ejecutar(["findmnt", "-rno", "TARGET", "-t", "ext4,btrfs,xfs,vfat,ntfs3,exfat"]) or "").splitlines():
        candidatas += [Path(linea) / ".Trash" / str(uid), Path(linea) / f".Trash-{uid}"]
    detalle, rutas = [], []
    for p in candidatas:
        if not p.is_dir():
            continue
        peso, _ = ctx.medir(p)
        ctx.reclamar(p)
        if peso and peso >= MINIMO:
            detalle.append(Item(str(p).replace(str(ctx.home), "~"), peso, p))
            rutas.append(p)
    if not detalle:
        return []
    return [Hallazgo(
        tr("Home"), tr("Papelera"), Nivel.REVISAR, sum(i.peso or 0 for i in detalle),
        tr("Cosas que ya mandaste a la papelera (también lo que mandó ArchCleaner). Vaciarla es "
          "definitivo y son archivos tuyos, por eso no viene tildada: echale un vistazo antes."),
        rutas=rutas, detalle=detalle, limpieza=Limpieza(Modo.VACIAR, por_item=True),
    )]


def _descargas_viejas(ctx: Contexto) -> list[Hallazgo]:
    descargas = Path((ejecutar(["xdg-user-dir", "DOWNLOAD"]) or "").strip() or ctx.home / "Descargas")
    if not descargas.is_dir() or descargas == ctx.home:
        return []
    limite = time.time() - DIAS_DESCARGA_VIEJA * 86400
    detalle, rutas = [], []
    for e in os.scandir(descargas):
        try:
            st = e.stat(follow_symlinks=False)
        except OSError:
            continue
        if st.st_mtime > limite:
            continue
        peso = ctx.medir(e.path)[0] if e.is_dir(follow_symlinks=False) else st.st_blocks * 512
        if peso and peso >= MINIMO:
            detalle.append(Item(e.name, peso, Path(e.path)))
            rutas.append(Path(e.path))
    if not detalle:
        return []
    return [Hallazgo(
        tr("Home"), tr("Descargas de hace más de {n} días", n=DIAS_DESCARGA_VIEJA), Nivel.REVISAR,
        sum(i.peso or 0 for i in detalle),
        tr("Instaladores, ISOs, comprimidos... cosas que bajaste hace rato y probablemente ya usaste."),
        rutas=rutas, detalle=items_ordenados(detalle),
        limpieza=Limpieza(Modo.PAPELERA, por_item=True),
    )]


def _normalizar(nombre: str) -> str:
    return re.sub(r"[^a-z0-9]", "", nombre.lower())


def _nombres_conocidos(ctx: Contexto) -> set[str]:
    """Todo nombre que "existe" en el sistema: paquetes, archivos que instalaron, apps Flatpak,
    programas en el PATH (ej. instalados a mano en ~/.local/bin) y juegos de Steam."""
    conocidos = {_normalizar(n) for n in ctx.nombres_conocidos}
    for carpeta in os.environ.get("PATH", "").split(":"):
        try:
            for e in os.scandir(carpeta):
                conocidos.add(_normalizar(e.name))
                # "hydra.AppImage", "Godot_v4-stable.x86_64" -> "hydra", "godot"
                conocidos.add(_normalizar(re.split(r"[._\- ]", e.name)[0]))
        except OSError:
            pass
    for p in (ejecutar(["pacman", "-Qq"]) or "").split():
        conocidos.add(_normalizar(p))
    for linea in (ejecutar(["pacman", "-Qlq"]) or "").splitlines():
        base = os.path.basename(linea.rstrip("/"))
        conocidos.add(_normalizar(base.removesuffix(".desktop")))
        if "." in base:  # org.kde.dolphin -> dolphin
            conocidos.add(_normalizar(base.removesuffix(".desktop").rsplit(".", 1)[-1]))
    for app in (ejecutar(["flatpak", "list", "--app", "--columns=application"]) or "").split():
        conocidos.add(_normalizar(app))
        conocidos.add(_normalizar(app.rsplit(".", 1)[-1]))
    conocidos |= {_normalizar(g) for g in GENERICAS}
    conocidos.discard("")
    return conocidos


def _parece_conocido(nombre: str, conocidos: set[str]) -> bool:
    n = _normalizar(nombre)
    if not n or n in conocidos:
        return True
    # "BraveSoftware" ~ "brave", "JetBrains" ~ "jetbrains-toolbox"
    return any(len(c) >= 4 and (n.startswith(c) or c.startswith(n)) for c in conocidos if c[:2] == n[:2])


def _restos(ctx: Contexto) -> list[Hallazgo]:
    conocidos = _nombres_conocidos(ctx)
    detalle, rutas = [], []
    for base in (ctx.home / ".config", ctx.home / ".local/share", ctx.home):
        if not base.is_dir():
            continue
        for d in base.iterdir():
            if base == ctx.home and not d.name.startswith("."):
                continue  # en el home solo miramos carpetas ocultas (.minecraft, .mozilla...)
            if d.name in (".config", ".local", ".cache", ".var") or not d.is_dir() or d.is_symlink():
                continue
            if _reclamada(ctx, os.path.realpath(d)) or _parece_conocido(d.name, conocidos):
                continue
            peso, _ = ctx.medir(d)
            if peso and peso >= MINIMO_RESTO:
                detalle.append(Item(str(d).replace(str(ctx.home), "~"), peso, d))
                rutas.append(d)
    if not detalle:
        return []
    return [Hallazgo(
        tr("Home"), tr("Posibles restos de programas que ya no están"), Nivel.REVISAR,
        sum(i.peso or 0 for i in detalle),
        tr("Carpetas de configuración/datos cuyo nombre no coincide con nada instalado. Es una "
          "suposición por nombre: puede ser de un AppImage, un programa portable o algo que usás. "
          "Revisá una por una."),
        rutas=rutas, detalle=items_ordenados(detalle),
        limpieza=Limpieza(Modo.PAPELERA, por_item=True),
    )]
