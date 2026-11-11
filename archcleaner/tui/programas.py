"""Pantalla para elegir qué programa desinstalar, con buscador. No toca nada (clic o enter elige).

Cada programa lleva su semáforo (ficha.semaforo): 🟢 se puede · 🟡 no recomendado · 🔴 ArchCleaner no lo
desinstala. Abajo, el motivo del resaltado. ? o el botón = 🤖 qué es (IA local, si hay Ollama; solo explica)."""

from __future__ import annotations

import asyncio
import time

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from ..estado import leer, guardar_preferencia
from .. import ia
from ..ficha import semaforo
from ..programas import ORDENES, Programa, hace, ordenar
from ..util import acortar, humano
from .comunes import ESPACIO, barra_botones
from .que_es import QueEsEsto, datos_de_programa
from ..i18n import tr


class ElegirProgramaScreen(Screen[Programa | str | None]):
    """Devuelve el programa elegido, None si se cancela, o "actualizar" para volver a leer la lista."""

    BINDINGS = [
        Binding("escape", "salir", tr("Salir"), priority=True),
        Binding("f5", "actualizar", tr("Actualizar"), priority=True),
        Binding("f2", "siguiente_orden", tr("Ordenar"), priority=True),
        Binding("down", "a_lista", show=False),
        Binding("question_mark", "que_es", tr("¿Qué es esto? (IA local)")),  # en el buscador, ? se escribe
    ]

    def __init__(self, programas: list[Programa], busqueda: str = ""):
        super().__init__()
        self.programas = programas
        self.busqueda_inicial = busqueda
        self.visibles: list[Programa] = []
        self.semaforos = {id(p): semaforo(p) for p in programas}
        self.con_ia = False
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
            yield Static(id="motivo", classes="motivo")
        yield barra_botones([("elegir", tr("Ver ficha ▸"), "primary"), ("que_es", tr("🤖 ¿Qué es?"), "default"), ESPACIO,
                             ("actualizar", tr("🔄 Actualizar"), "default"), ("cancelar", tr("Cancelar"), "default")])

    def on_mount(self) -> None:
        self._dibujar_orden()
        self.query_one("#que_es", Button).add_class("oculto")
        self._filtrar(self.busqueda_inicial)
        self.query_one(Input).focus()
        self._buscar_ia()

    @work
    async def _buscar_ia(self) -> None:
        """El botón 🤖 aparece solo si hay un Ollama respondiendo."""
        if await asyncio.to_thread(ia.disponible):
            self.con_ia = True
            self.query_one("#que_es", Button).remove_class("oculto")
            self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        return self.con_ia if action == "que_es" else True

    def _resaltado(self) -> Programa | None:
        lista = self.query_one(OptionList)
        return self.visibles[lista.highlighted] if self.visibles and lista.highlighted is not None else None

    def action_que_es(self) -> None:
        if not self.con_ia or not (p := self._resaltado()):
            return
        if p.origen == "steam":  # sin descripción, la IA les inventa el argumento; y el juego ya lo conocés
            self.notify(tr("Con juegos de Steam la IA inventa demasiado: buscalo en la tienda de Steam."))
            return
        self.app.push_screen(QueEsEsto(datos_de_programa(p)))

    def on_option_list_option_highlighted(self, ev: OptionList.OptionHighlighted) -> None:
        self._mostrar_motivo()

    def _mostrar_motivo(self) -> None:
        p = self._resaltado()
        motivo = self.query_one("#motivo", Static)
        if p is None:
            motivo.update("")
            return
        color, texto = self.semaforos[id(p)]
        if color == "verde":
            motivo.update(Text.assemble(("🟢 " + tr("Se puede desinstalar: antes vas a ver la ficha."), "green"),
                                        ("   ·   🟡 " + tr("no recomendado") + "   ·   🔴 "
                                         + tr("ArchCleaner no lo desinstala"), "dim")))
        else:
            motivo.update(Text(f"{ICONOS[color]} {texto}", style="yellow" if color == "amarillo" else "red"))

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
        if ev.button.id == "que_es":
            self.action_que_es()
            return
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
        self._mostrar_motivo()

    def _fila(self, p: Programa, ancho_desc: int) -> Text:
        origen, color = p.etiqueta_origen
        semaforo_ = self.semaforos[id(p)][0]
        fila = Text.assemble(
            (f"{humano(p.peso):>9}  ", "bold"),
            _celda_uso(p), "  ",
            (f" {origen:^8} ", f"bold {color} reverse"), "  ",
            (ICONOS[semaforo_] + " ", ""),
            (acortar(p.nombre, 32).ljust(32), "dim" if semaforo_ == "rojo" else "bold"), "  ",
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


ICONOS = {"verde": "🟢", "amarillo": "🟡", "rojo": "🔴"}


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
