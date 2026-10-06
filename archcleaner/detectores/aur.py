"""AUR: cachés de compilación de yay y paru."""

from __future__ import annotations

from ..contexto import Contexto
from ..modelo import Hallazgo, Limpieza, Modo, Nivel
from ..i18n import tr

MINIMO = 20 * 1024**2


def detectar(ctx: Contexto) -> list[Hallazgo]:
    res = []
    for helper, sub in (("yay", ".cache/yay"), ("paru", ".cache/paru")):
        carpeta = ctx.home / sub
        if not carpeta.is_dir():
            continue
        ctx.reclamar(carpeta)
        peso, inc = ctx.medir(carpeta)
        if not peso or peso < MINIMO:
            continue
        res.append(Hallazgo(
            tr("AUR"), tr("Caché de compilación de {helper}", helper=helper), Nivel.SEGURO, peso,
            tr("{helper} guarda acá el código y los paquetes que compiló del AUR. "
              "Se vuelve a descargar si actualizás o reinstalás algo.", helper=helper),
            rutas=[carpeta], limpieza=Limpieza(Modo.VACIAR), incompleto=inc,
        ))
    return res
