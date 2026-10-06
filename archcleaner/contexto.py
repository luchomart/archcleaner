"""Contexto compartido entre detectores: escaneos ya hechos y una forma barata de medir carpetas."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .escaner import ResultadoEscaneo, escanear


@dataclass
class Contexto:
    home: Path = field(default_factory=Path.home)
    escaneos: list[ResultadoEscaneo] = field(default_factory=list)
    reclamadas: set[str] = field(default_factory=set)  # rutas que ya reportó algún detector
    steam_bibliotecas: list[Path] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    etiquetas: dict[str, str] = field(default_factory=dict)  # ruta -> nombre legible (ej. juego de Steam)
    nombres_conocidos: set[str] = field(default_factory=set)  # nombres que NO son restos (ej. juegos instalados)

    def medir(self, ruta: Path | str) -> tuple[int | None, bool]:
        """(bytes, incompleto). Reusa los escaneos grandes si la ruta ya fue recorrida."""
        r = os.path.realpath(ruta)
        if not os.path.exists(r):
            return None, False
        if not os.path.isdir(r):
            try:
                return os.lstat(r).st_blocks * 512, False
            except OSError:
                return None, True
        for esc in self.escaneos:
            if esc.contiene(r) and r in esc.total:
                return esc.total[r], esc.incompleto(r)
        esc = escanear(r, umbral_grande=1 << 62)
        return esc.peso, bool(esc.sin_permiso)

    def reclamar(self, ruta: Path | str) -> None:
        self.reclamadas.add(os.path.realpath(ruta))
