"""Pantalla para elegir qué programa desinstalar, con buscador. No toca nada (clic o enter elige)."""

from __future__ import annotations

import time

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from ..estado import leer, guardar_preferencia
from ..ficha import PROTEGIDOS
from ..programas import ORDENES, Programa, hace, ordenar
from ..util import acortar, humano
from .comunes import ESPACIO, barra_botones
from ..i18n import tr


class ElegirProgramaScreen(Screen[Programa | str | None]):
    """Devuelve el programa elegido, None si se cancela, o "actualizar" para volver a leer la lista."""

    BINDINGS = [
        Binding("escape", "salir", tr("Salir"), priority=True),
        Binding("f5", "actualizar", tr("Actualizar"), priority=True),
        Binding("f2", "siguiente_orden", tr("Ordenar"), priority=True),
        Binding("down", "a_lista", show=False),
    ]

    def __init__(self, programas: list[Programa], busqueda: str = ""):
        super().__init__()
        self.programas = programas
        self.busqueda_inicial = busqueda
        self.visibles: list[Programa] = []
        orden = leer().get("preferencias", {}).get("orden_programas", "tamano")
        self.orden = orden if orden in ORDENES else "tamano"

    def compose(self) -> ComposeResult:
        yield Static(Text.assemble(
            (tr("📦 Desinstalar"), "bold cyan"), ("   ·   ", "dim"),
            (tr("{n} programas instalados", n=len(self.programas)), "bold"),
            (tr("\nElegir no desinstala nada: primero vas a ver la ficha completa."), "dim"),
        ), classes="cabecera")
        with Vertical():
            yield Input(value=self.busqueda_inicial, placeholder=tr("🔎 Escribí para buscar (nombre, descripción, origen)…"),
                        id="buscar")
            yield Static(id="orden", classes="orden")
            yield OptionList(id="lista", classes="lista")
        yield barra_botones([("elegir", tr("Ver ficha ▸"), "primary"), ESPACIO,
                             ("actualizar", tr("🔄 Actualizar"), "default"), ("cancelar", tr("Cancelar"), "default")])

    def on_mount(self) -> None:
        self._dibujar_orden()
        self._filtrar(self.busqueda_inicial)
        self.query_one(Input).focus()

    # ── orden ──

    def _dibujar_orden(self) -> None:
        partes = ["[dim]" + tr("Ordenar por:") + "[/]  "]
        for clave, (texto, _) in ORDENES.items():
            if clave == self.orden:
                partes.append(f"[bold reverse cyan] {texto} [/]  ")
            else:
                partes.append(f"[@click=screen.ordenar('{clave}')][cyan] {texto} [/][/]  ")
        partes.append("[dim](F2)[/]")
        if self.orden == "uso":
            aclaracion = tr("«sin uso» = no se abrió desde que se instaló o actualizó")
            if self.size.width >= 80 + len(aclaracion):  # si no entra, no se muestra
                partes.append(f"   [dim]{aclaracion}[/]")
        self.query_one("#orden", Static).update("".join(partes))

    def on_resize(self) -> None:
        self._dibujar_orden()

    def action_ordenar(self, clave: str) -> None:
        if clave not in ORDENES or clave == self.orden:
            return
        self.orden = clave
        guardar_preferencia("orden_programas", clave)
        self._dibujar_orden()
        self._filtrar(self.query_one(Input).value)

    def action_siguiente_orden(self) -> None:
        claves = list(ORDENES)
        self.action_ordenar(claves[(claves.index(self.orden) + 1) % len(claves)])

    def on_input_changed(self, ev: Input.Changed) -> None:
        self._filtrar(ev.value)

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        if self.visibles:
            self.dismiss(self.visibles[0])

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id in ("cancelar", "actualizar"):
            self.dismiss(None if ev.button.id == "cancelar" else "actualizar")
            return
        lista = self.query_one(OptionList)
        if self.visibles and lista.highlighted is not None:
            self.dismiss(self.visibles[lista.highlighted])

    def _filtrar(self, texto: str) -> None:
        palabras = texto.lower().split()
        self.visibles = ordenar([p for p in self.programas
                                 if all(w in f"{p.nombre} {p.id} {p.descripcion} {p.origen}".lower() for w in palabras)],
                                self.orden)
        lista = self.query_one(OptionList)
        ancho_desc = max(10, self.size.width - 86)  # lo que sobra después de peso, uso, origen y nombre
        lista.set_options([Option(self._fila(p, ancho_desc), id=str(i)) for i, p in enumerate(self.visibles)])
        if self.visibles:
            lista.highlighted = 0

    @staticmethod
    def _fila(p: Programa, ancho_desc: int) -> Text:
        origen, color = p.etiqueta_origen
        fila = Text.assemble(
            (f"{humano(p.peso):>9}  ", "bold"),
            _celda_uso(p), "  ",
            (f" {origen:^8} ", f"bold {color} reverse"), "  ",
            ("🔒 " if p.origen in ("repo", "aur") and p.id in PROTEGIDOS else "   ", ""),
            (acortar(p.nombre, 32).ljust(32), "dim" if p.id in PROTEGIDOS else "bold"), "  ",
            (p.descripcion if len(p.descripcion) <= ancho_desc else p.descripcion[: ancho_desc - 1] + "…", "grey62"),
        )
        return fila

    def action_a_lista(self) -> None:
        if self.focused is self.query_one(Input):
            self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, ev: OptionList.OptionSelected) -> None:
        self.dismiss(self.visibles[int(ev.option.id or 0)])

    def action_salir(self) -> None:
        self.dismiss(None)

    def action_actualizar(self) -> None:
        self.dismiss("actualizar")

    def action_atras(self) -> None:
        self.dismiss(None)


def _celda_uso(p: Programa) -> tuple[str, str]:
    """La columna «último uso» (12 caracteres): verde si es reciente, amarillo si hace mucho o nunca."""
    if p.ultimo_uso:
        texto = hace(p.ultimo_uso)
        dias = (time.time() - p.ultimo_uso) / 86400
        estilo = "green" if dias < 7 else "default" if dias < 60 else "yellow"
    elif p.uso_conocido:
        texto, estilo = (tr("nunca jugado") if p.origen == "steam" else tr("sin uso")), "yellow"
    else:
        texto, estilo = "—", "grey42"
    return f"{texto:>12}", estilo
