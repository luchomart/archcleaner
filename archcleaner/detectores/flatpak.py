"""Flatpak: runtimes que ninguna app usa y datos de apps ya desinstaladas (~/.var/app)."""

from __future__ import annotations

from ..contexto import Contexto
from ..modelo import Hallazgo, Item, Limpieza, Modo, Nivel, items_ordenados
from ..util import ejecutar, parsear_tamano
from ..i18n import tr

MINIMO = 10 * 1024**2


def detectar(ctx: Contexto) -> list[Hallazgo]:
    res: list[Hallazgo] = []
    hay_flatpak = ejecutar(["which", "flatpak"]) is not None
    apps = set((ejecutar(["flatpak", "list", "--app", "--columns=application"]) or "").split()) if hay_flatpak else set()

    if hay_flatpak and (h := _runtimes_sin_uso(apps)):
        res.append(h)

    var_app = ctx.home / ".var/app"
    if var_app.is_dir():
        detalle, rutas, incompleto = [], [], False
        for d in sorted(var_app.iterdir()):
            if not d.is_dir() or d.name in apps:
                continue
            peso, inc = ctx.medir(d)
            incompleto |= inc
            if peso and peso >= MINIMO:
                detalle.append(Item(d.name, peso, d))
                rutas.append(d)
                ctx.reclamar(d)
        if detalle:
            detalle = items_ordenados(detalle)
            res.append(Hallazgo(
                tr("Flatpak"), tr("Datos de apps Flatpak que ya no están instaladas"), Nivel.REVISAR,
                sum(i.peso or 0 for i in detalle),
                tr("Al desinstalar un Flatpak sin --delete-data, sus datos quedan en ~/.var/app. "
                  "Puede haber partidas guardadas o configs que quieras conservar: mirá antes de borrar."),
                rutas=rutas, detalle=detalle, limpieza=Limpieza(Modo.PAPELERA, por_item=True),
                incompleto=incompleto,
            ))
    return res


def _runtimes_sin_uso(apps: set[str]) -> Hallazgo | None:
    """Runtimes que ninguna app instalada necesita (lo mismo que `flatpak uninstall --unused`)."""
    sal = ejecutar(["flatpak", "list", "--runtime", "--columns=application,branch,size"]) or ""
    runtimes = []
    for linea in sal.splitlines():
        partes = linea.split("\t")
        if len(partes) >= 3:
            runtimes.append((partes[0], partes[1], parsear_tamano(partes[2])))
    if not runtimes:
        return None

    usados: set[str] = set()
    for app in apps:
        info = ejecutar(["flatpak", "info", "--show-runtime", app]) or ""
        if info.strip():
            usados.add(info.strip().split("/")[0])
    # Las extensiones (ej. org.freedesktop.Platform.GL.default) cuelgan del nombre del runtime.
    sin_uso = [r for r in runtimes if not any(r[0] == u or r[0].startswith(u + ".") for u in usados)]
    if not sin_uso:
        return None
    return Hallazgo(
        tr("Flatpak"), tr("Runtimes de Flatpak que ninguna app usa"), Nivel.SEGURO,
        sum(r[2] or 0 for r in sin_uso),
        tr("Son las 'bases' que necesitan las apps Flatpak. Estas no las usa ninguna app instalada."),
        detalle=[Item(f"{n} ({b})", tam) for n, b, tam in sin_uso],
        limpieza=Limpieza(Modo.COMANDO, [["flatpak", "uninstall", "--unused", "-y"]]),
    )
