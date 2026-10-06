"""📈 Qué creció: compara el último análisis con uno anterior (elegido con un clic)."""

from __future__ import annotations

from datetime import datetime

from rich.console import Group
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from .. import historial
from ..historial import Foto
from ..util import humano
from .comunes import ACTUALIZAR, ESPACIO, barra_botones, cabecera

# (clave, texto, días atrás; None = el análisis anterior)
OPCIONES = [("anterior", "Análisis anterior", None), ("semana", "Hace 1 semana", 7), ("mes", "Hace 1 mes", 30)]


class CrecioScreen(Screen[str | None]):
    """Devuelve "actualizar" (analizar de nuevo y volver), "atras" o None."""

    BINDINGS = [Binding("escape", "volver", "Inicio"), Binding("r,f5", "actualizar", "Actualizar"),
                Binding("f2", "siguiente", "Comparar con…")]

    def __init__(self, actual: Foto):
        super().__init__()
        self.actual = actual
        self.modo = "anterior"
        self.fecha_elegida: float | None = None

    def compose(self) -> ComposeResult:
        yield cabecera("📈 Qué creció", f"Último análisis: {self.actual.cuando}. Solo lectura: no se toca nada.")
        yield Static(id="comparar", classes="orden")
        with VerticalScroll(classes="cuerpo"):
            yield Static(id="contenido")
        yield barra_botones([ESPACIO, ACTUALIZAR, ("volver", "🏠 Inicio", "primary")])

    def on_mount(self) -> None:
        self._mostrar()
        self.query_one(VerticalScroll).focus()

    def _base(self) -> Foto | None:
        if self.modo == "fecha" and self.fecha_elegida:
            return next((historial.cargar(r) for f, r in historial.listar() if f == self.fecha_elegida), None)
        dias = dict((k, d) for k, _, d in OPCIONES).get(self.modo)
        return historial.anterior(self.actual.fecha, dias)

    def _mostrar(self) -> None:
        partes = ["[dim]Comparar con:[/]  "]
        for clave, texto, _ in [*OPCIONES, ("fecha", "📅 Otra fecha…", None)]:
            if clave == self.modo and clave != "fecha":
                partes.append(f"[bold reverse cyan] {texto} [/]  ")
            else:
                partes.append(f"[@click=screen.comparar('{clave}')][cyan] {texto} [/][/]  ")
        partes.append("[dim](F2)[/]")
        self.query_one("#comparar", Static).update("".join(partes))

        base = self._base()
        contenido = self.query_one("#contenido", Static)
        if base is None:
            contenido.update(historial.sin_historial(len(historial.listar())))
            return
        comp = historial.comparar(base, self.actual)
        piezas = historial.paneles(comp)
        dias = dict((k, d) for k, _, d in OPCIONES).get(self.modo)
        if dias and comp.dias < dias - 1:
            piezas.insert(0, Text(f"El análisis más viejo que hay es del {base.cuando}: comparo con ese.",
                                  style="yellow"))
        contenido.update(Group(*piezas))

    def action_comparar(self, clave: str) -> None:
        if clave == "fecha":
            self._elegir_fecha()
            return
        self.modo = clave
        self._mostrar()

    @work
    async def _elegir_fecha(self) -> None:
        fecha = await self.app.push_screen_wait(ElegirFoto(self.actual))
        if fecha:
            self.modo, self.fecha_elegida = "fecha", fecha
            self._mostrar()

    def action_siguiente(self) -> None:
        claves = [k for k, _, _ in OPCIONES]
        self.modo = claves[(claves.index(self.modo) + 1) % len(claves)] if self.modo in claves else claves[0]
        self._mostrar()

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss("actualizar" if ev.button.id == "actualizar" else None)

    def action_actualizar(self) -> None:
        self.dismiss("actualizar")

    def action_volver(self) -> None:
        self.dismiss(None)

    def action_atras(self) -> None:
        self.dismiss("atras")


class ElegirFoto(ModalScreen[float | None]):
    """Lista de análisis guardados para comparar contra uno en particular."""

    BINDINGS = [Binding("escape", "cancelar", "Cancelar")]

    def __init__(self, actual: Foto):
        super().__init__()
        self.fechas = [f for f, _ in historial.listar() if f < int(actual.fecha)][::-1]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialogo"):
            yield Static(Text("📅 ¿Con qué análisis comparo?", style="bold"), classes="dialogo-titulo")
            if self.fechas:
                yield OptionList(*[Option(self._fila(f), id=str(i)) for i, f in enumerate(self.fechas)],
                                 id="fotos", classes="lista")
            else:
                yield Static(Text("No hay análisis anteriores guardados.", style="dim"))
            yield barra_botones([ESPACIO, ("cancelar", "Cancelar", "default")])

    @staticmethod
    def _fila(f: float) -> Text:
        foto = historial.cargar(next(r for t, r in historial.listar() if t == f))
        libre = foto.discos.get("/", [0, 0])[1] if foto else 0
        return Text.assemble(
            (datetime.fromtimestamp(f).strftime(" %d/%m/%Y  %H:%M"), "bold"),
            (f"   {historial.hace_dias((datetime.now().timestamp() - f) / historial.DIA)}", "dim"),
            (f"   libre en /: {humano(libre)}" if libre else "", "grey62"),
        )

    def on_option_list_option_selected(self, ev: OptionList.OptionSelected) -> None:
        self.dismiss(self.fechas[int(ev.option.id or 0)])

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(None)

    def action_cancelar(self) -> None:
        self.dismiss(None)
