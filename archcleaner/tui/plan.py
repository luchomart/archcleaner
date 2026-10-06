"""Pantalla del plan: lo que se va a hacer, papelera o definitivo, snapshot opcional, y el botón final."""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, RadioButton, RadioSet, Static

from ..acciones import Tarea
from ..limpiar import panel_definitivo
from ..modelo import Modo
from ..util import humano
from .comunes import ESPACIO, ConfirmarBorrado, ElegirGrupos, barra_botones, cabecera
from ..i18n import tr


@dataclass
class Decision:
    snapshot: bool = False


class PlanScreen(Screen[Decision | None]):
    """Devuelve la decisión (y marca `definitivo` en las tareas elegidas), o None si se cancela."""

    BINDINGS = [Binding("escape", "cancelar", tr("Cancelar"))]

    def __init__(self, titulo: str, panel, tareas: list[Tarea], simulacro: bool = False,
                 snapshot: bool | None = None, boton: str = tr("🧹 Ejecutar")):
        super().__init__()
        self.titulo, self.panel, self.tareas = titulo, panel, tareas
        self.simulacro, self.snapshot, self.boton = simulacro, snapshot, boton
        self.a_papelera = [t for t in tareas if t.modo == Modo.PAPELERA]

    def compose(self) -> ComposeResult:
        sub = tr("SIMULACRO: podés mirar todo, pero no se va a ejecutar nada.") if self.simulacro \
            else tr("Todavía no se tocó nada. Revisá y confirmá abajo.")
        yield cabecera(self.titulo, sub)
        with VerticalScroll(classes="cuerpo"):
            yield Static(self.panel)
            if self.a_papelera:
                peso = sum(t.peso for t in self.a_papelera)
                yield Static(Text.assemble((tr("\n🗑  Lo que va a la papelera suma "), "bold"),
                                           (humano(peso), "bold yellow"), (tr(". ¿Qué hacemos con eso?"), "bold")))
                with RadioSet(id="destino"):
                    yield RadioButton(tr("Papelera: se puede recuperar (el espacio se libera al vaciarla)"), value=True)
                    yield RadioButton(tr("Definitivo: libera el espacio ya, no se puede deshacer"))
                    yield RadioButton(tr("Elegir grupo por grupo"))
            if self.snapshot is not None:
                yield Static(Text(tr("\n🕒 Timeshift"), style="bold"))
                yield Checkbox(tr("Crear una snapshot antes (para poder volver atrás si algo sale mal)"),
                               value=self.snapshot, id="snapshot")
        botones = [ESPACIO, ("volver", tr("🏠 Inicio"), "primary")] if self.simulacro else \
            [("ejecutar", self.boton, "success"), ESPACIO, ("volver", tr("Cancelar"), "default")]
        yield barra_botones(botones)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "ejecutar":
            self.confirmar()
        else:
            self.dismiss(None)

    @work
    async def confirmar(self) -> None:
        if self.a_papelera:
            opcion = self.query_one("#destino", RadioSet).pressed_index
            elegidas: list[Tarea] = []
            if opcion == 1:
                elegidas = self.a_papelera
            elif opcion == 2:
                textos = [f"{t.hallazgo.titulo}  ({humano(t.peso)})" for t in self.a_papelera]
                indices = await self.app.push_screen_wait(ElegirGrupos(textos))
                if indices is None:
                    return
                elegidas = [self.a_papelera[i] for i in indices]
            if elegidas and await self.app.push_screen_wait(ConfirmarBorrado(panel_definitivo(elegidas))):
                for t in elegidas:
                    t.definitivo = True
            elif elegidas:
                self.notify(tr("No se confirmó el borrado definitivo: eso va a la papelera."), severity="warning")
        snapshot = self.snapshot is not None and self.query_one("#snapshot", Checkbox).value
        self.dismiss(Decision(snapshot=snapshot))

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def action_atras(self) -> None:
        self.dismiss("atras")  # type: ignore[arg-type]
