"""Tipos de datos compartidos: qué es un hallazgo, qué tan seguro es tocarlo y cómo se limpia."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Nivel(Enum):
    SEGURO = "seguro"    # se regenera solo, borrarlo no rompe nada
    REVISAR = "revisar"  # pesa y probablemente sobra, pero decide el usuario
    INFO = "info"        # solo informativo, no se toca desde acá

    @property
    def icono(self) -> str:
        return {"seguro": "🟢", "revisar": "🟡", "info": "🔵"}[self.value]

    @property
    def color(self) -> str:
        return {"seguro": "green", "revisar": "yellow", "info": "blue"}[self.value]

    @property
    def nombre(self) -> str:
        return {
            "seguro": "Basura segura",
            "revisar": "Para revisar",
            "info": "Solo informativo",
        }[self.value]


class Modo(Enum):
    BORRAR = "borrar"      # se borra directo (basura que se regenera sola)
    VACIAR = "vaciar"      # se borra el contenido, la carpeta queda
    PAPELERA = "papelera"  # se mueve a la papelera (recuperable)
    COMANDO = "comando"    # se usa la herramienta oficial (paccache, journalctl, pacman...)


@dataclass
class Item:
    """Un sub-elemento de un hallazgo. Si tiene `ruta` o `comando`, al limpiar se puede elegir de a uno."""
    nombre: str
    peso: int | None
    ruta: Path | None = None
    comando: list[str] | None = None  # para ítems que se limpian con un comando (ej. borrar una snapshot)

    @property
    def elegible(self) -> bool:
        return self.ruta is not None or self.comando is not None


@dataclass
class Limpieza:
    modo: Modo
    comandos: list[list[str]] = field(default_factory=list)  # solo para COMANDO
    sudo: bool = False
    por_item: bool = False          # al limpiar se eligen los ítems del detalle uno por uno
    cerrar: list[str] = field(default_factory=list)  # procesos que tienen que estar cerrados (ej. steam)
    nota: str | None = None         # aviso antes de ejecutar
    texto: str | None = None        # descripción corta si el comando es muy largo

    def describir(self) -> str:
        if self.texto:
            return self.texto
        if self.modo == Modo.COMANDO:
            return " ; ".join(shlex.join(c) for c in self.comandos)
        return {
            Modo.BORRAR: "se borra (se regenera solo)",
            Modo.VACIAR: "se vacía el contenido",
            Modo.PAPELERA: "va a la papelera (recuperable)",
        }[self.modo]


@dataclass
class Hallazgo:
    categoria: str          # "Pacman", "Steam", "Sistema"...
    titulo: str
    nivel: Nivel
    peso: int | None        # bytes que se liberarían (None = no se pudo medir)
    explicacion: str
    rutas: list[Path] = field(default_factory=list)
    detalle: list[Item] = field(default_factory=list)
    limpieza: Limpieza | None = None
    incompleto: bool = False    # hubo carpetas sin permiso: el peso real puede ser mayor
    suma: bool = True           # False = no cuenta en el total "liberable" (ej. archivos gigantes)
    numero: int = 0             # lo asigna el análisis para poder referirse a él (#3)


def items_ordenados(items: list[Item]) -> list[Item]:
    return sorted(items, key=lambda i: i.peso or 0, reverse=True)
