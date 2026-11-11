"""🙈 "No mostrar más": confirmar antes de ocultar y la lista de lo oculto para volver a mostrarlo."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

from .. import ignorados
from ..i18n import tr
from ..util import humano
from .comunes import ESPACIO, Dialogo, barra_botones


def _corta(ruta: str | Path) -> str:
    return str(ruta).replace(str(Path.home()), "~", 1)


async def confirmar_ocultar(app: App, rutas: list[Path], peso: int | None) -> bool:
    """¿Seguro? Ocultar no borra nada, pero deja de proponerlo en todos los análisis siguientes."""
    lista = "\n".join(f"  • {_corta(r)}" for r in rutas[:8]) + (f"\n  … (+{len(rutas) - 8})" if len(rutas) > 8 else "")
    cuerpo = Text.assemble(
        (lista, "bold"), (f"  ({humano(peso)})" if peso else "", "dim"),
        (tr("\n\nNo se borra nada. ArchCleaner deja de proponerlo para borrar (también lo que tenga adentro), "
            "en este y en los próximos análisis.\nLo podés volver a mostrar desde «🙈 Ocultos»."), "dim"))
    r = await app.push_screen_wait(Dialogo(tr("🙈 No mostrar más"), cuerpo,
                                           [("si", tr("🙈 No mostrar más"), "primary"), ("no", tr("Cancelar"), "default")]))
    return r == "si"


class Ocultos(ModalScreen[list[str] | None]):
    """Lo oculto, con casillas: devuelve las rutas a volver a mostrar (None si se cierra)."""

    BINDINGS = [Binding("escape", "cerrar", tr("Cerrar"))]

    def __init__(self) -> None:
        super().__init__()
        self.ocultos = ignorados.lista()

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialogo"):
            yield Static(Text(tr("🙈 Ocultos"), style="bold"), classes="dialogo-titulo")
            yield Static(Text(tr("ArchCleaner no te propone borrar nada de esto. Tildá lo que quieras volver a ver: "
                                 "aparece de nuevo en el próximo análisis (🔄 Actualizar)."), style="dim"))
            with VerticalScroll(classes="dialogo-cuerpo"):
                if not self.ocultos:
                    yield Static(Text(tr("(no hay nada oculto)"), style="dim"))
                for i, o in enumerate(self.ocultos):
                    try:
                        fecha = datetime.fromisoformat(o["fecha"]).strftime(tr("%d/%m/%Y"))
                    except (KeyError, ValueError):
                        fecha = ""
                    detalle = " · ".join(x for x in (o.get("que", ""), fecha) if x)
                    yield Checkbox(f"{_corta(o['ruta'])}" + (f"   ({detalle})" if detalle else ""), id=f"o{i}")
            yield barra_botones([("mostrar", tr("👁 Volver a mostrar"), "primary"), ESPACIO,
                                 ("cerrar", tr("Cerrar"), "default")])

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id != "mostrar":
            self.dismiss(None)
            return
        self.dismiss([o["ruta"] for i, o in enumerate(self.ocultos) if self.query_one(f"#o{i}", Checkbox).value])

    def action_cerrar(self) -> None:
        self.dismiss(None)
