"""🙈 "No mostrar más": rutas que el usuario no quiere que se le propongan para borrar.

Ocultar una ruta oculta también todo lo que tiene adentro. Se guarda en estado.json ("ocultos") y se
aplica al final de cada análisis (y a los restos de una desinstalación), así que tampoco aparece marcado
en Explorar ni en el informe. Ocultar solo hace que se proponga borrar MENOS: nunca agrega nada.

Cuidado: un hallazgo que no se elige de a un ítem borra todas sus rutas (o corre un comando, como
paccache). Si lo oculto está adentro de una de esas rutas, sacarlo de la lista no alcanza: el hallazgo
pasa a ser 🔵 informativo (no se propone limpiar) y avisa por qué.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from . import estado
from .i18n import tr
from .modelo import Hallazgo, Nivel
from .util import dentro_de


def normal(ruta: str | Path) -> str:
    return os.path.normpath(os.path.abspath(os.path.expanduser(str(ruta))))


def lista() -> list[dict]:
    """[{"ruta": ..., "fecha": ..., "que": ...}], lo más nuevo primero."""
    ocultos = estado.leer().get("ocultos", [])
    return [o for o in ocultos if isinstance(o, dict) and o.get("ruta")]


def rutas() -> list[str]:
    return [o["ruta"] for o in lista()]


def ocultar(nuevas: Sequence[str | Path], que: str = "") -> None:
    actuales = lista()
    ya = {o["ruta"] for o in actuales}
    fecha = datetime.now().isoformat(timespec="seconds")
    agregar = [{"ruta": r, "fecha": fecha, "que": que} for r in dict.fromkeys(map(normal, nuevas)) if r not in ya]
    estado.guardar_ocultos(agregar + actuales)


def mostrar(volver: Sequence[str | Path]) -> None:
    sacar = set(map(normal, volver))
    estado.guardar_ocultos([o for o in lista() if o["ruta"] not in sacar])


def oculta(ruta: str | Path, ocultos: list[str] | None = None) -> str | None:
    """La ruta oculta que la cubre (ella misma o una carpeta de arriba), o None."""
    r = normal(ruta)
    reales = {r, os.path.realpath(r)}
    for o in rutas() if ocultos is None else ocultos:
        if any(dentro_de(x, o) for x in reales):
            return o
    return None


def _oculto_adentro(ruta: str | Path, ocultos: list[str]) -> str | None:
    """Una ruta oculta que está ADENTRO de `ruta` (borrar `ruta` la borraría)."""
    r = normal(ruta)
    reales = {r, os.path.realpath(r)}
    return next((o for o in ocultos if any(dentro_de(o, x) and o != x for x in reales)), None)


def aplicar(hallazgos: list[Hallazgo], ocultos: list[str] | None = None) -> list[Hallazgo]:
    """Saca de `hallazgos` (la misma lista, modificada) lo oculto. Devuelve la lista."""
    ocultos = rutas() if ocultos is None else ocultos
    if not ocultos:
        return hallazgos
    quedan = []
    for h in hallazgos:
        if not h.limpieza:  # informativos (peso de cada juego, árbol...): no proponen borrar nada
            quedan.append(h)
            continue
        if h.limpieza.por_item:
            if _filtrar_items(h, ocultos):
                quedan.append(h)
            continue
        tapadas = [r for r in h.rutas if oculta(r, ocultos)]
        adentro = next((o for r in h.rutas if (o := _oculto_adentro(r, ocultos))), None)
        if h.rutas and len(tapadas) == len(h.rutas):
            continue  # todo el hallazgo está oculto
        if tapadas or adentro:
            # no se puede limpiar a medias (borra todas sus rutas o corre un comando): queda solo informativo
            motivo = adentro or oculta(tapadas[0], ocultos)
            h.limpieza = None
            h.nivel = Nivel.INFO
            h.suma = False
            h.explicacion += " " + tr("Tiene algo que ocultaste ({ruta}), así que no se propone limpiarlo.",
                                      ruta=motivo)
        quedan.append(h)
    hallazgos[:] = quedan
    return hallazgos


def _filtrar_items(h: Hallazgo, ocultos: list[str]) -> bool:
    """Saca los ítems ocultos (o que tienen algo oculto adentro). False si no queda nada para elegir."""
    sacar = [it for it in h.detalle if it.ruta and (oculta(it.ruta, ocultos) or _oculto_adentro(it.ruta, ocultos))]
    if not sacar:
        return True
    fuera = {id(it) for it in sacar}
    h.detalle = [it for it in h.detalle if id(it) not in fuera]
    h.rutas = [r for r in h.rutas if not oculta(r, ocultos)]
    if h.peso is not None:
        h.peso = max(0, h.peso - sum(it.peso or 0 for it in sacar))
    return any(it.elegible for it in h.detalle)
