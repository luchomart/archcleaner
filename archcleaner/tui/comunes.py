"""Piezas reusables de la app: progreso, vistas con scroll, diálogos con botones."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Input, LoadingIndicator, ProgressBar, Static
from ..i18n import tr

# (id, texto, variante) de cada botón. Un id "-" es un espacio flexible: lo que sigue va a la derecha.
Botones = list[tuple[str, str, str]]
ESPACIO = ("-", "", "")


def cabecera(titulo: str, subtitulo: str = "") -> Static:
    return Static(Text.assemble((titulo, "bold cyan"), (f"\n{subtitulo}" if subtitulo else "", "dim")),
                  classes="cabecera")


def barra_botones(botones: Botones) -> Horizontal:
    hijos = [Static(classes="espacio") if id_ == "-" else Button(texto, variant=var, id=id_)
             for id_, texto, var in botones]
    return Horizontal(*hijos, classes="botones")


class Progreso(Screen[None]):
    """Algo tarda: spinner + qué está haciendo. Con `barra=True`, una barra con % y tiempo restante."""

    def __init__(self, titulo: str, barra: bool = False):
        super().__init__()
        self.titulo, self.con_barra = titulo, barra

    def compose(self) -> ComposeResult:
        with Center(classes="progreso"):
            yield Static(Text(self.titulo, style="bold cyan"), classes="progreso-titulo")
            if self.con_barra:
                yield Static("", id="etapa", classes="progreso-etapa")
                with Center():
                    yield ProgressBar(total=1000, show_eta=True, id="barra")
            else:
                yield LoadingIndicator()
            yield Static("", id="detalle", classes="progreso-detalle")

    def avisar(self, texto: str) -> None:
        self.query_one("#detalle", Static).update(Text(texto[:120], style="dim"))

    def avanzar(self, fraccion: float, etapa: str, detalle: str = "") -> None:
        self.query_one("#etapa", Static).update(Text(etapa, style="bold"))
        self.query_one("#barra", ProgressBar).update(progress=round(fraccion * 1000))
        self.avisar(detalle)


class Vista(Screen[str | None]):
    """Contenido largo con scroll (informe, ficha, resultado) y botones abajo.

    Si entre los botones hay uno "actualizar", F5 o r hacen lo mismo.
    """

    BINDINGS = [Binding("escape", "volver", tr("Volver")), Binding("r,f5", "actualizar", tr("Actualizar"))]

    def __init__(self, titulo: str, contenido: list, botones: Botones, subtitulo: str = ""):
        super().__init__()
        self.titulo, self.subtitulo = titulo, subtitulo
        self.contenido, self.botones = contenido, botones

    def compose(self) -> ComposeResult:
        yield cabecera(self.titulo, self.subtitulo)
        with VerticalScroll(classes="cuerpo"):
            for r in self.contenido:
                yield Static(r)
        yield barra_botones(self.botones)

    def on_mount(self) -> None:
        self.query_one(VerticalScroll).focus()

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(ev.button.id)

    def action_volver(self) -> None:
        self.dismiss(None)

    def action_actualizar(self) -> None:
        if any(b[0] == "actualizar" for b in self.botones):
            self.dismiss("actualizar")

    def action_atras(self) -> None:
        self.dismiss("atras")


ACTUALIZAR = ("actualizar", tr("🔄 Actualizar"), "default")


class Dialogo(ModalScreen[str | None]):
    """Ventana flotante con un mensaje y botones. Devuelve el id del botón (None si se cierra con esc)."""

    BINDINGS = [Binding("escape", "cerrar", tr("Cerrar"))]

    def __init__(self, titulo: str, cuerpo, botones: Botones, estilo: str = ""):
        super().__init__()
        self.titulo, self.cuerpo, self.botones = titulo, cuerpo, botones
        self.estilo = estilo

    def compose(self) -> ComposeResult:
        with Vertical(classes=f"dialogo {self.estilo}"):
            yield Static(Text(self.titulo, style="bold"), classes="dialogo-titulo")
            with VerticalScroll(classes="dialogo-cuerpo"):
                yield Static(self.cuerpo)
            yield barra_botones(self.botones)

    def on_mount(self) -> None:
        self.query(Button).first().focus()

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(ev.button.id)

    def action_cerrar(self) -> None:
        self.dismiss(None)


PALABRA = tr("borrar")  # lo que hay que escribir para confirmar un borrado definitivo («delete» en inglés)


class ConfirmarBorrado(ModalScreen[bool]):
    """Última palabra antes de borrar PARA SIEMPRE: hay que escribir PALABRA (el botón se habilita solo así)."""

    BINDINGS = [Binding("escape", "cancelar", tr("Cancelar"))]

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialogo peligro"):
            yield Static(Text(tr("🔥 Borrado definitivo"), style="bold red"), classes="dialogo-titulo")
            with VerticalScroll(classes="dialogo-cuerpo"):
                yield Static(self.panel)
            yield Static(Text.assemble(tr("Esto "), (tr("no se puede deshacer"), "bold red"),
                                       tr(". Para confirmar, escribí "), (PALABRA, "bold red"), ":"))
            yield Input(placeholder=PALABRA, id="palabra")
            yield barra_botones([("si", tr("🔥 Borrar para siempre"), "error"),
                                 ("no", tr("🗑 Mejor a la papelera"), "default")])

    def on_mount(self) -> None:
        self.query_one("#si", Button).disabled = True
        self.query_one(Input).focus()

    def on_input_changed(self, ev: Input.Changed) -> None:
        self.query_one("#si", Button).disabled = ev.value.strip().lower() != PALABRA

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        if ev.value.strip().lower() == PALABRA:
            self.dismiss(True)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(ev.button.id == "si")

    def action_cancelar(self) -> None:
        self.dismiss(False)


class ElegirGrupos(ModalScreen[list[int] | None]):
    """Casillas para elegir qué grupos se borran definitivamente (el resto va a la papelera)."""

    BINDINGS = [Binding("escape", "cancelar", tr("Cancelar"))]

    def __init__(self, opciones: list[str]):
        super().__init__()
        self.opciones = opciones

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialogo"):
            yield Static(Text(tr("¿Qué se borra definitivamente?"), style="bold"), classes="dialogo-titulo")
            yield Static(Text(tr("Lo que no tildes va a la papelera."), style="dim"))
            with VerticalScroll(classes="dialogo-cuerpo"):
                for i, texto in enumerate(self.opciones):
                    yield Checkbox(texto, id=f"g{i}")
            yield barra_botones([("ok", tr("Seguir ▸"), "primary"), ("no", tr("Cancelar"), "default")])

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id != "ok":
            self.dismiss(None)
            return
        self.dismiss([i for i in range(len(self.opciones)) if self.query_one(f"#g{i}", Checkbox).value])

    def action_cancelar(self) -> None:
        self.dismiss(None)
