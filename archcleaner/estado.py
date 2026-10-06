"""Resumen persistente para el menú de inicio: último análisis y última limpieza."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .modelo import Hallazgo, Nivel
from .i18n import tr

ARCHIVO = Path.home() / ".local/state/archcleaner/estado.json"
LOG = Path.home() / ".local/state/archcleaner/acciones.log"


def leer() -> dict:
    try:
        return json.loads(ARCHIVO.read_text())
    except (OSError, ValueError):
        return {}


def _escribir(clave: str, valor: dict) -> None:
    datos = leer()
    datos[clave] = valor
    try:
        ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=2))
    except OSError:
        pass


def guardar_analisis(hallazgos: list[Hallazgo]) -> None:
    def total(nivel: Nivel) -> int:
        return sum(h.peso or 0 for h in hallazgos if h.nivel == nivel and h.suma)

    principales = sorted((h for h in hallazgos if h.nivel != Nivel.INFO and h.suma),
                         key=lambda h: h.peso or 0, reverse=True)[:3]
    _escribir("analisis", {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "seguro": total(Nivel.SEGURO),
        "revisar": total(Nivel.REVISAR),
        "cantidad": len(hallazgos),
        "principales": [[h.nivel.icono, h.titulo, h.peso or 0] for h in principales],
    })


def guardar_preferencia(clave: str, valor) -> None:
    """Cosas que la app recuerda entre una vez y otra (ej. cómo ordenar la lista de programas)."""
    preferencias = leer().get("preferencias", {})
    preferencias[clave] = valor
    _escribir("preferencias", preferencias)


def tiempos_previos() -> dict:
    """Cuánto pesó y tardó cada parte del análisis la última vez (para estimar la barra de avance)."""
    return leer().get("tiempos", {})


def guardar_tiempos(tiempos: dict) -> None:
    """Se mezcla con lo anterior: un análisis rápido (sin discos) no borra lo que tardaron los discos."""
    previos = tiempos_previos()
    con_discos = bool(tiempos.get("raices"))
    _escribir("tiempos", {
        "raices": {**previos.get("raices", {}), **tiempos.get("raices", {})},
        # sin escanear discos, los detectores tienen que medir solos y tardan distinto: no sirve de referencia
        "detectores": tiempos.get("detectores") if con_discos else previos.get("detectores"),
    })


def guardar_limpieza(liberado: int, tareas_ok: int, tareas_total: int) -> None:
    _escribir("limpieza", {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "liberado": liberado,
        "ok": tareas_ok,
        "total": tareas_total,
    })


def ultima_limpieza() -> dict | None:
    """La última limpieza guardada; si no hay, se reconstruye desde el log de acciones
    (tareas de los 30 min previos a la última anotada, con el peso estimado)."""
    datos = leer().get("limpieza")
    if datos:
        return datos
    try:
        entradas = [json.loads(linea) for linea in LOG.read_text().splitlines() if linea.strip()]
    except (OSError, ValueError):
        return None
    if not entradas:
        return None
    ultima = datetime.fromisoformat(entradas[-1]["fecha"])
    sesion = [e for e in entradas if (ultima - datetime.fromisoformat(e["fecha"])).total_seconds() <= 1800]
    return {
        "fecha": entradas[-1]["fecha"],
        "liberado": sum(e.get("peso_estimado", 0) for e in sesion if e.get("ok")),
        "ok": sum(1 for e in sesion if e.get("ok")),
        "total": len(sesion),
        "estimado": True,
    }


def hace(fecha_iso: str) -> str:
    """'hace 5 min', 'hace 3 h', 'ayer', 'hace 4 días'."""
    try:
        seg = (datetime.now() - datetime.fromisoformat(fecha_iso)).total_seconds()
    except ValueError:
        return "?"
    if seg < 60:
        return tr("recién")
    if seg < 3600:
        return tr("hace {n} min", n=int(seg // 60))
    if seg < 86400:
        return tr("hace {n} h", n=int(seg // 3600))
    dias = int(seg // 86400)
    return tr("ayer") if dias == 1 else tr("hace {n} días", n=dias)
