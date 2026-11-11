"""🤖 La ventana "¿Qué es esto?" (IA local). La usan Explorar y la pantalla para elegir qué limpiar."""

from __future__ import annotations

import asyncio
import os
import stat
import subprocess
import urllib.parse
from collections.abc import Callable
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, LoadingIndicator, Static

from .. import i18n, ia
from ..i18n import tr
from ..util import ejecutar as correr
from ..util import humano


def paquetes_dueños(ruta: str) -> list[str]:
    """Paquetes que instalaron esa ruta, como "pacman 7.1.0-1" (pacman -Qo: una carpeta puede tener varios)."""
    salida = correr(["pacman", "-Qo", "--", ruta], timeout=10) or ""
    return [dueño for linea in salida.splitlines() if (dueño := linea.partition(" is owned by ")[2].strip())]


class QueEsEsto(ModalScreen[None]):
    """🤖 La IA local explica qué es algo. Solo lectura: no hay ningún botón para borrar desde acá."""

    BINDINGS = [Binding("escape", "cerrar", tr("Cerrar"))]

    def __init__(self, datos: ia.Datos):
        super().__init__()
        self.datos = datos

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialogo"):
            yield Static(Text(tr("🤖 ¿Qué es esto?"), style="bold"), classes="dialogo-titulo")
            yield Static(Text.assemble(("📁 " if self.datos.carpeta else "📄 ", ""), (self.datos.ruta, "bold"),
                                       (f"  ({self.datos.peso})", "dim")))
            yield LoadingIndicator(id="pensando")
            yield Static(Text(tr("La primera vez tarda más: Ollama carga el modelo."), style="dim"), id="primera")
            with VerticalScroll(classes="dialogo-cuerpo"):
                yield Static(id="respuesta")
            yield Static(Text(tr("Explicación generada por IA local ({modelo}): puede equivocarse. "
                                 "No cambia lo que ArchCleaner marca como 🟢 o 🟡.", modelo=ia.modelo()),
                              style="dim italic"), id="aviso-ia")
            with Horizontal(classes="botones"):
                yield Button(tr("🔎 Buscar en internet"), id="buscar", classes="oculto")
                yield Static(classes="espacio")
                yield Button(tr("Cerrar"), id="cerrar", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#cerrar", Button).focus()
        self._preguntar()

    @work
    async def _preguntar(self) -> None:
        respuesta = self.query_one("#respuesta", Static)
        try:
            r = await asyncio.to_thread(ia.preguntar, self.datos, i18n.idioma)
            texto = Text("\n").join(Text(x) for x in ia.lineas(r, self.datos))
            duda = not r.conocido
        except ia.SinIA as e:
            texto, duda = Text(str(e), style="yellow"), False
        if self.is_attached:
            self.query_one("#pensando").display = False
            self.query_one("#primera").display = False
            respuesta.update(texto)
            if duda:  # la IA no lo conoce: que el usuario lo busque él (solo sale el nombre, y solo si aprieta)
                self.query_one("#buscar", Button).remove_class("oculto")

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "buscar":
            abrir_navegador(url_busqueda(self.datos.ruta))
            self.notify(tr("Abriendo el navegador…"))
            return
        self.dismiss(None)

    def action_cerrar(self) -> None:
        self.dismiss(None)


def abrir_navegador(url: str) -> None:
    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def url_busqueda(ruta: str) -> str:
    """Búsqueda web con el NOMBRE (nunca la ruta entera: tiene tu usuario y nombres de tus carpetas)."""
    nombre = os.path.basename(ruta.rstrip("/")) or ruta
    return "https://duckduckgo.com/?q=" + urllib.parse.quote_plus(f'"{nombre}" linux')


def datos_de(ruta: str | Path, peso: int | None, peso_carpeta: Callable[[str], int | None] = lambda _: None,
             contexto: str = "") -> ia.Datos:
    """Arma lo que se le cuenta a la IA de una ruta cualquiera (para pantallas que no listan la carpeta).
    `peso_carpeta`: el peso medido de una subcarpeta, si se sabe (del último análisis)."""
    ruta = str(ruta)
    carpeta = os.path.isdir(ruta) and not os.path.islink(ruta)
    adentro = None
    if carpeta:
        filas: list[tuple[str, int | None]] = []
        try:
            for e in os.scandir(ruta):
                try:
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                es_dir = stat.S_ISDIR(st.st_mode)
                filas.append((e.name + ("/" if es_dir else ""), peso_carpeta(e.path) if es_dir else st.st_blocks * 512))
        except OSError:
            pass
        filas.sort(key=lambda x: (x[1] is None, -(x[1] or 0), x[0].lower()))
        adentro = [(nombre, humano(p)) for nombre, p in filas[:ia.MAX_ADENTRO]]
    return ia.Datos(ruta.replace(str(Path.home()), "~", 1), carpeta, humano(peso), paquetes_dueños(ruta), adentro,
                    contexto)
