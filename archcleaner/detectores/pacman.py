"""Pacman: caché de paquetes, paquetes huérfanos y archivos .pacnew/.pacsave."""

from __future__ import annotations

import os
import re
from pathlib import Path

from ..contexto import Contexto
from ..modelo import Hallazgo, Item, Limpieza, Modo, Nivel, items_ordenados
from ..util import ejecutar, humano, parsear_tamano
from ..i18n import tr

CACHE = Path("/var/cache/pacman/pkg")


def detectar(ctx: Contexto) -> list[Hallazgo]:
    res: list[Hallazgo] = []
    res += _cache(ctx)
    if h := _huerfanos():
        res.append(h)
    if h := _debug():
        res.append(h)
    if h := _pacsave():
        res.append(h)
    return res


def _dry_run_paccache(args: list[str]) -> tuple[int, int]:
    """(cantidad, bytes) que borraría paccache, sin borrar nada (-d = dry run)."""
    sal = ejecutar(["paccache", "-d", *args]) or ""
    m = re.search(r"(\d+) candidates? \(disk space saved: ([^)]+)\)", sal)
    if not m:
        return 0, 0
    return int(m.group(1)), parsear_tamano(m.group(2)) or 0


def _cache(ctx: Contexto) -> list[Hallazgo]:
    if not CACHE.is_dir():
        return []
    ctx.reclamar(CACHE)
    total, _ = ctx.medir(CACHE)
    res = []
    if ejecutar(["which", "paccache"]) is None:
        ctx.avisos.append(tr("No está instalado pacman-contrib (paccache): no se puede analizar la caché de pacman."))
        return res

    n, b = _dry_run_paccache(["-k2"])
    if n:
        res.append(Hallazgo(
            tr("Pacman"), tr("Versiones viejas en la caché de paquetes"), Nivel.SEGURO, b,
            tr("Pacman guarda cada versión que descargó (la caché pesa {total} en total). "
              "Se conservan las 2 últimas de cada paquete por si una actualización sale mal y "
              "necesitás volver atrás; se borran {n} versiones más viejas.", total=humano(total), n=n),
            rutas=[CACHE], limpieza=Limpieza(Modo.COMANDO, [["paccache", "-rk2"]], sudo=True),
        ))
    n, b = _dry_run_paccache(["-uk0"])
    if n:
        res.append(Hallazgo(
            tr("Pacman"), tr("Caché de paquetes que ya desinstalaste"), Nivel.SEGURO, b,
            tr("{n} archivos de paquetes que ya no tenés instalados.", n=n),
            rutas=[CACHE], limpieza=Limpieza(Modo.COMANDO, [["paccache", "-ruk0"]], sudo=True),
        ))
    return res


def _huerfanos() -> Hallazgo | None:
    nombres = (ejecutar(["pacman", "-Qdtq"]) or "").split()
    if not nombres:
        return None
    info = ejecutar(["pacman", "-Qi", *nombres]) or ""
    detalle: list[Item] = []
    nombre = None
    for linea in info.splitlines():
        if linea.startswith("Name"):
            nombre = linea.split(":", 1)[1].strip()
        elif linea.startswith("Installed Size") and nombre:
            detalle.append(Item(nombre, parsear_tamano(linea.split(":", 1)[1])))
            nombre = None
    detalle = items_ordenados(detalle)
    return Hallazgo(
        tr("Pacman"), tr("Paquetes huérfanos"), Nivel.REVISAR, sum(i.peso or 0 for i in detalle),
        tr("Se instalaron como dependencia de algo que ya desinstalaste y nadie más los usa. "
          "Ojo: si alguno lo usás vos directamente (por ejemplo un compilador), quedátelo."),
        detalle=detalle,
        limpieza=Limpieza(Modo.COMANDO, [["pacman", "-Rns", *nombres]], sudo=True,
                          nota=tr("pacman te va a mostrar la lista y pedir confirmación.")),
    )


def _info_paquetes(nombres: list[str]) -> list[Item]:
    """[(nombre, tamaño instalado)] de una lista de paquetes."""
    info = ejecutar(["pacman", "-Qi", *nombres]) or ""
    res: list[Item] = []
    nombre = None
    for linea in info.splitlines():
        if linea.startswith("Name"):
            nombre = linea.split(":", 1)[1].strip()
        elif linea.startswith("Installed Size") and nombre:
            res.append(Item(nombre, parsear_tamano(linea.split(":", 1)[1])))
            nombre = None
    return items_ordenados(res)


def _debug() -> Hallazgo | None:
    """Paquetes -debug que makepkg genera al compilar del AUR con OPTIONS=(... debug ...)."""
    nombres = [p for p in (ejecutar(["pacman", "-Qq"]) or "").split() if p.endswith("-debug")]
    if not nombres:
        return None
    detalle = _info_paquetes(nombres)
    return Hallazgo(
        tr("AUR"), tr("Paquetes de depuración (-debug)"), Nivel.SEGURO, sum(i.peso or 0 for i in detalle),
        tr("Símbolos para depurar programas compilados del AUR. Solo sirven si vas a investigar un cuelgue "
          "con gdb. Se crean porque /etc/makepkg.conf tiene la opción «debug»: para que no se generen más, "
          "creá ~/.config/pacman/makepkg.conf con la línea  OPTIONS+=(!debug)"),
        detalle=detalle,
        limpieza=Limpieza(Modo.COMANDO, [["pacman", "-Rns", *nombres]], sudo=True,
                          nota=tr("pacman te va a mostrar la lista y pedir confirmación.")),
    )


def _pacsave() -> Hallazgo | None:
    encontrados: list[Item] = []
    for raiz, dirs, archivos in os.walk("/etc", onerror=lambda e: None):
        for a in archivos:
            if a.endswith((".pacnew", ".pacsave")):
                p = os.path.join(raiz, a)
                try:
                    encontrados.append(Item(p, os.lstat(p).st_blocks * 512))
                except OSError:
                    encontrados.append(Item(p, None))
    if not encontrados:
        return None
    return Hallazgo(
        tr("Pacman"), tr("Configs .pacnew / .pacsave pendientes"), Nivel.REVISAR,
        sum(i.peso or 0 for i in encontrados),
        tr(".pacsave = config de un programa desinstalado que pacman guardó por las dudas (resto). "
          ".pacnew = config nueva que trajo una actualización y no se aplicó. No ocupan casi nada, "
          "pero conviene revisarlas (con `pacdiff`, de pacman-contrib)."),
        detalle=encontrados, suma=False,
    )
