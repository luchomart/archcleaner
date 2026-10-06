"""Menú de inicio: lo que aparece al escribir `archcleaner` solo.

No hace nada pesado: lee el uso de los discos y el resumen guardado del último análisis/limpieza.
Al elegir una opción le avisa a la app (que arranca el flujo); al volver, se actualiza solo.
"""

from __future__ import annotations

import os
import shutil

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from .. import __author__, __version__
from ..estado import hace, leer, ultima_limpieza
from ..historial import chispa, libre_en_el_tiempo
from ..util import humano
from ..i18n import tr

# Fuente "Calvin S" de figlet, letra por letra.
_LETRAS = {
    "A": ("╔═╗", "╠═╣", "╩ ╩"), "R": ("╦═╗", "╠╦╝", "╩╚═"), "C": ("╔═╗", "║  ", "╚═╝"),
    "H": ("╦ ╦", "╠═╣", "╩ ╩"), "L": ("╦  ", "║  ", "╩═╝"), "E": ("╔═╗", "║╣ ", "╚═╝"),
    "N": ("╔╗╔", "║║║", "╝╚╝"),
}
_DEGRADE = ["#5fd7ff", "#5fafff", "#5f87ff", "#875fff", "#af5fff"]

OPCIONES = [
    # (id, ícono, nombre, descripción, atajo, disponible)
    ("analizar", "🔍", tr("Analizar"), tr("informe completo de qué ocupa espacio · solo lectura"), "a", True),
    ("limpiar", "🧹", tr("Limpiar"), tr("elegís qué borrar, ves el plan y confirmás"), "l", True),
    ("simulacro", "🧪", tr("Simulacro"), tr("lo mismo que Limpiar, pero sin borrar nada"), "s", True),
    ("desinstalar", "📦", tr("Desinstalar"), tr("un programa sin dejar rastro · con ficha y plan"), "d", True),
    ("actualizar", "🔄", tr("Actualizar"), tr("vuelve a analizar el disco y refresca las tarjetas"), "r", True),
    ("explorar", "📂", tr("Explorar"), tr("navegar carpetas ordenadas por peso (y borrar)"), "e", True),
    ("crecio", "📈", tr("Qué creció"), tr("comparar con análisis anteriores: qué creció y qué se achicó"), "c", True),
    ("salir", "🚪", tr("Salir"), "", "q", True),
]


def logo() -> Text:
    palabra = "ARCHCLEANER"
    t = Text()
    for fila in range(3):
        for i, letra in enumerate(palabra):
            t.append(_LETRAS[letra][fila], style=f"bold {_DEGRADE[i * len(_DEGRADE) // len(palabra)]}")
        t.append("\n")
    t.append(tr("analizador y limpiador de disco para Arch Linux"), style="dim")
    t.append(f"  ·  v{__version__}  ·  ", style="dim")
    t.append(f"by {__author__}", style="italic #af87ff")
    return t


def _color_uso(f: float) -> str:
    return "red" if f >= 0.9 else "yellow" if f >= 0.75 else "green"


def _barra(f: float, ancho: int) -> Text:
    llenos = round(max(0.0, min(1.0, f)) * ancho)
    return Text("━" * llenos, style=_color_uso(f)) + Text("━" * (ancho - llenos), style="grey23")


def _puntos_montaje() -> list[str]:
    puntos = ["/"]
    for base in ("/mnt", "/media", f"/run/media/{os.environ.get('USER', '')}"):
        try:
            puntos += [e.path for e in os.scandir(base) if e.is_dir() and os.path.ismount(e.path)]
        except OSError:
            pass
    return puntos


def tarjeta_discos() -> Table:
    t = Table.grid(padding=(0, 1))
    t.add_column(style="bold")
    t.add_column()
    t.add_column(justify="right")
    for p in _puntos_montaje():
        try:
            u = shutil.disk_usage(p)
        except OSError:
            continue
        f = u.used / u.total if u.total else 0
        t.add_row(p, _barra(f, 10) + Text(f" {f:>4.0%}", style=_color_uso(f)),
                  Text.assemble((humano(u.free) + " ", "bold"), (tr("libres"), "dim")))
    return t


def subtitulo_discos() -> str | None:
    """Mini gráfica del espacio libre en / según los últimos análisis: «libre en / ▆▆▅▄»."""
    valores = libre_en_el_tiempo("/")
    return tr("libre en / {grafica}", grafica=chispa(valores)) if len(valores) >= 2 else None


def tarjeta_analisis(datos: dict) -> Text | Group:
    a = datos.get("analisis")
    if not a:
        cuerpo: Text | Group = Text(tr("Todavía no analizaste.\nElegí 🔍 Analizar."), style="dim")
    else:
        filas = Table.grid(padding=(0, 1))
        filas.add_column()
        filas.add_column(justify="right")
        filas.add_row(Text(tr("🟢 sin riesgo"), style="green"), Text(humano(a["seguro"]), style="bold green"))
        filas.add_row(Text(tr("🟡 si revisás"), style="yellow"), Text(humano(a["revisar"]), style="bold yellow"))
        principal = a.get("principales", [])[:1]
        extra = Text(f"\n{principal[0][1]}", style="dim", overflow="ellipsis", no_wrap=True) \
            if principal else Text("")
        cuerpo = Group(filas, extra)
    return cuerpo


def tarjeta_limpieza(lim: dict | None) -> Text:
    if not lim:
        cuerpo = Text(tr("Todavía no limpiaste nada."), style="dim")
    else:
        cuerpo = Text.assemble(
            ("~" if lim.get("estimado") else "", "bold green"),
            (humano(lim["liberado"]) + " ", "bold green"), (tr("liberados") + "\n\n", ""),
            (tr("{ok} de {total} tareas ok", ok=lim["ok"], total=lim["total"]), "dim"),
        )
    return cuerpo


class MenuScreen(Screen[None]):
    BINDINGS = [Binding(atajo, f"elegir('{id_}')", nombre, show=False)
                for id_, _, nombre, _, atajo, disponible in OPCIONES if disponible] + [
        Binding("escape", "elegir('salir')", tr("Salir"), show=False),
    ]

    def compose(self) -> ComposeResult:
        datos = leer()
        with Vertical(id="todo"):
            yield Static(logo(), id="logo")
            with Horizontal(id="tarjetas"):
                yield self._tarjeta("t-discos", tr("💽 Discos"), tarjeta_discos(), subtitulo_discos())
                a, lim = datos.get("analisis"), ultima_limpieza()
                yield self._tarjeta("t-analisis", tr("📊 Último análisis"), tarjeta_analisis(datos),
                                    hace(a["fecha"]) if a else None)
                yield self._tarjeta("t-limpieza", tr("✨ Última limpieza"), tarjeta_limpieza(lim),
                                    hace(lim["fecha"]) if lim else None)
            yield OptionList(*self._opciones(), id="menu")
            yield Static(Text.assemble(("↑↓ ", "bold"), tr("moverse    "), ("enter ", "bold"), tr("elegir    "),
                                       ("a l s d e c r ", "bold"), tr("atajos    "), ("q ", "bold"), tr("salir")),
                         id="pie")

    @staticmethod
    def _tarjeta(id_: str, titulo: str, contenido, subtitulo: str | None = None) -> Static:
        st = Static(contenido, id=id_)
        st.border_title = titulo
        if subtitulo:
            st.border_subtitle = subtitulo
        return st

    @staticmethod
    def _opciones() -> list[Option | None]:
        res: list[Option | None] = []
        for id_, icono, nombre, desc, atajo, disponible in OPCIONES:
            if id_ == "salir":
                res.append(None)
            prompt = Text.assemble(
                f" {icono}  ", (f"{nombre:<13}", "bold" if disponible else "dim"),
                (desc, "grey62" if disponible else "grey42"),
            )
            if disponible:
                prompt.append(f"   [{atajo}]", style="dim cyan")
            res.append(Option(prompt, id=id_, disabled=not disponible))
        return res

    def on_option_list_option_selected(self, ev: OptionList.OptionSelected) -> None:
        self.action_elegir(ev.option.id or "salir")

    def action_elegir(self, opcion: str) -> None:
        if opcion == "salir":
            self.app.exit()
        else:
            self.app.iniciar(opcion)  # type: ignore[attr-defined]

    def on_screen_resume(self) -> None:
        self.refresh(recompose=True)  # al volver de un flujo: discos y tarjetas actualizados
        self.call_after_refresh(lambda: self.query_one("#menu").focus())
