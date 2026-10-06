"""Botones laterales del mouse (atrás/adelante) → teclas Alt+← / Alt+→.

Las terminales que reportan esos botones los mandan como los botones 8 y 9 del protocolo SGR
(códigos 128 y 129). Textual no los conoce y los confundía con clic izquierdo/medio. Acá se
interceptan antes: atrás → Alt+←, adelante → Alt+→ (lo mismo que en un navegador). La app
decide qué hace cada uno en cada pantalla.
"""

from __future__ import annotations

from textual import events
from textual._xterm_parser import XTermParser

_original = XTermParser.parse_mouse_code


def _parse_mouse_code(self: XTermParser, code: str):
    sgr = self._re_sgr_mouse.match(code)
    if sgr:
        botones = int(sgr.group(1))
        if botones & 128 and not botones & 64:  # botones 8 a 11 (laterales), sin ser rueda
            if sgr.group(4) != "M":
                return None  # solo al apretar, no al soltar
            return events.Key("alt+left" if botones & 3 == 0 else "alt+right", None)
    return _original(self, code)


def activar() -> None:
    XTermParser.parse_mouse_code = _parse_mouse_code  # type: ignore[method-assign]
