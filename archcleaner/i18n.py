"""Idiomas: los textos del código están en español; `tr()` los traduce si la app corre en inglés.

El idioma sale del sistema (LANG, LC_ALL...): español si empieza con "es", inglés si no. Se puede
forzar con `archcleaner --lang en|es` o la variable de entorno ARCHCLEANER_LANG.

    tr("Hay {n} snapshots", n=3)   ->  "Hay 3 snapshots"  /  "There are 3 snapshots"

Si a un texto le falta la traducción, se muestra en español (nunca se rompe nada); el test
tests/test_i18n.py avisa si pasa.
"""

from __future__ import annotations

import os

IDIOMAS = ("es", "en")


def _detectar() -> str:
    forzado = os.environ.get("ARCHCLEANER_LANG", "").lower()[:2]
    if forzado in IDIOMAS:
        return forzado
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        valor = os.environ.get(var, "")
        if valor:
            return "es" if valor.lower().startswith("es") else "en"
    return "en"


idioma = _detectar()
_traducciones: dict[str, str] | None = None


def elegir(nuevo: str) -> None:
    """Cambia el idioma (antes de importar el resto de la app: hay textos que se arman al importar)."""
    global idioma
    if nuevo in IDIOMAS:
        idioma = nuevo


def tr(texto: str, **datos) -> str:
    if idioma != "es":
        global _traducciones
        if _traducciones is None:
            from .idiomas.en import TEXTOS
            _traducciones = TEXTOS
        texto = _traducciones.get(texto, texto)
    return texto.format(**datos) if datos else texto
