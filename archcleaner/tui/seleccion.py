"""Pantalla para tildar qué limpiar (o qué restos borrar). No borra nada: devuelve la selección.

Se usa con teclado (espacio, s, n, enter) o con el mouse (clic en una fila tilda/destilda, botones abajo).
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from ..modelo import Hallazgo, Nivel
from ..util import acortar, humano
from .comunes import ESPACIO, barra_botones

# Selección: número de hallazgo -> None (el hallazgo entero) o lista de índices del detalle.
Seleccion = dict[int, list[int] | None]


@dataclass
class Fila:
    hallazgo: Hallazgo
    item: int | None = None  # índice en hallazgo.detalle; None = fila del hallazgo


class SeleccionScreen(Screen[Seleccion | str | None]):
    """Devuelve la selección, None si se cancela, o "actualizar" para volver a buscar."""

    BINDINGS = [
        Binding("space", "tildar", "Tildar"),
        Binding("s", "solo_seguros", "Solo 🟢"),
        Binding("n", "ninguno", "Ninguno"),
        Binding("enter", "continuar", "Continuar", priority=True),
        Binding("escape", "salir", "Cancelar"),
        Binding("r,f5", "actualizar", "Actualizar"),
    ]

    def __init__(self, hallazgos: list[Hallazgo], titulo: str = "🧹 Elegí qué limpiar",
                 secciones: dict[Nivel, str] | None = None, previa: Seleccion | None = None):
        super().__init__()
        self.titulo = titulo
        self.secciones = secciones or {n: n.nombre for n in Nivel}
        self.hallazgos = [h for h in hallazgos if h.limpieza]
        self.filas: dict[str, Fila] = {}
        self.marcados: set[str] = set()
        if previa is None:
            self._solo_seguros()
        else:  # al volver atrás desde el plan: lo que ya habías tildado
            for h in self.hallazgos:
                if h.numero in previa:
                    elegidos = previa[h.numero]
                    self.marcados |= {f"h{h.numero}"} if elegidos is None else \
                        {f"h{h.numero}-{i}" for i in elegidos}

    # ── estado ──

    def _ids_de(self, h: Hallazgo) -> list[str]:
        if h.limpieza and h.limpieza.por_item:
            return [f"h{h.numero}-{i}" for i, it in enumerate(h.detalle) if it.elegible]
        return [f"h{h.numero}"]

    def _solo_seguros(self) -> None:
        self.marcados = {i for h in self.hallazgos if h.nivel == Nivel.SEGURO for i in self._ids_de(h)}

    def seleccion(self) -> Seleccion:
        res: Seleccion = {}
        for h in self.hallazgos:
            ids = [i for i in self._ids_de(h) if i in self.marcados]
            if not ids:
                continue
            res[h.numero] = [int(i.rsplit("-", 1)[1]) for i in ids] if h.limpieza.por_item else None  # type: ignore[union-attr]
        return res

    def total(self) -> int:
        tot = 0
        for h in self.hallazgos:
            for i in self._ids_de(h):
                if i in self.marcados:
                    tot += (h.detalle[int(i.rsplit("-", 1)[1])].peso or 0) if "-" in i else (h.peso or 0)
        return tot

    # ── armado ──

    def compose(self) -> ComposeResult:
        yield Static(id="cabecera", classes="cabecera")
        with Vertical():
            yield OptionList(id="lista", classes="lista")
            yield Static(id="info", classes="info")
        yield barra_botones([("continuar", "Continuar ▸", "success"), ("seguros", "Solo 🟢", "default"),
                             ("ninguno", "Ninguno", "default"), ESPACIO,
                             ("actualizar", "🔄 Actualizar", "default"), ("cancelar", "Cancelar", "default")])

    def on_mount(self) -> None:
        self._redibujar()
        lista = self.query_one(OptionList)
        lista.focus()
        lista.highlighted = next((i for i, o in enumerate(lista.options) if not o.disabled), None)

    def _redibujar(self) -> None:
        lista = self.query_one(OptionList)
        resaltado = lista.highlighted
        opciones: list[Option | None] = []
        self.filas.clear()
        for nivel in (Nivel.SEGURO, Nivel.REVISAR):
            grupo = [h for h in self.hallazgos if h.nivel == nivel]
            if not grupo:
                continue
            if opciones:
                opciones.append(None)
            opciones.append(Option(Text(f" {nivel.icono}  {self.secciones[nivel].upper()}", style=f"bold {nivel.color}"),
                                   disabled=True))
            for h in grupo:
                opciones += self._opciones_de(h)
        lista.set_options(opciones)
        if resaltado is not None:
            lista.highlighted = resaltado
        self._actualizar_cabecera()

    def _opciones_de(self, h: Hallazgo) -> list[Option]:
        ids = self._ids_de(h)
        n = sum(i in self.marcados for i in ids)
        marca = "✔" if n == len(ids) else "–" if n else " "
        sudo = Text(" sudo", style="bold magenta") if h.limpieza.sudo else Text("")  # type: ignore[union-attr]
        fila_id = f"g{h.numero}" if h.limpieza.por_item else ids[0]  # type: ignore[union-attr]
        self.filas[fila_id] = Fila(h)
        opciones = [Option(Text.assemble(
            self._caja(marca, h.nivel.color), f"{humano(h.peso):>9}  ", (h.titulo, "bold"), sudo,
        ), id=fila_id)]
        if h.limpieza.por_item:  # type: ignore[union-attr]
            for i in ids:
                k = int(i.rsplit("-", 1)[1])
                item = h.detalle[k]
                self.filas[i] = Fila(h, k)
                opciones.append(Option(Text.assemble(
                    "      ", self._caja("✔" if i in self.marcados else " ", h.nivel.color),
                    (f"{humano(item.peso):>9}  ", "dim"), acortar(item.nombre, 72),
                ), id=i))
        return opciones

    @staticmethod
    def _caja(marca: str, color: str) -> Text:
        return Text.assemble(("[", "grey50"), (marca, f"bold {color}"), ("] ", "grey50"))

    def _actualizar_cabecera(self) -> None:
        sel = self.seleccion()
        self.query_one("#cabecera", Static).update(Text.assemble(
            (self.titulo, "bold cyan"),
            ("   ·   ", "dim"), (f"{len(sel)} grupos", "bold"),
            ("   ·   ", "dim"), ("seleccionado: ", "dim"), (humano(self.total()), "bold green"),
            ("\nNada se borra todavía: después vas a ver el plan y confirmar.   ", "dim"),
            ("clic o espacio: ", "bold"), ("tildar/destildar", "dim"),
        ))

    def on_option_list_option_highlighted(self, ev: OptionList.OptionHighlighted) -> None:
        fila = self.filas.get(ev.option.id or "")
        info = self.query_one("#info", Static)
        if not fila:
            info.update("")
            return
        h = fila.hallazgo
        texto = Text.assemble((f"#{h.numero} {h.titulo}", f"bold {h.nivel.color}"), "\n", (h.explicacion, "grey70"))
        lim = h.limpieza
        assert lim
        texto.append("\n▸ ", style=h.nivel.color)
        texto.append(lim.describir())
        if lim.cerrar:
            texto.append(f"   (con {', '.join(lim.cerrar)} cerrado)", style="yellow")
        if lim.nota:
            texto.append(f"\n⚠ {lim.nota}", style="yellow")
        info.update(texto)

    # ── acciones ──

    def on_option_list_option_selected(self, ev: OptionList.OptionSelected) -> None:
        self.action_tildar()

    def action_tildar(self) -> None:
        lista = self.query_one(OptionList)
        if lista.highlighted is None:
            return
        opcion = lista.get_option_at_index(lista.highlighted)
        fila = self.filas.get(opcion.id or "")
        if not fila:
            return
        if fila.item is None:  # fila del hallazgo: tilda/destilda todos sus ítems
            ids = self._ids_de(fila.hallazgo)
            if all(i in self.marcados for i in ids):
                self.marcados -= set(ids)
            else:
                self.marcados |= set(ids)
        else:
            self.marcados ^= {opcion.id}  # type: ignore[arg-type]
        self._redibujar()

    def action_solo_seguros(self) -> None:
        self._solo_seguros()
        self._redibujar()

    def action_ninguno(self) -> None:
        self.marcados.clear()
        self._redibujar()

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        {"continuar": self.action_continuar, "seguros": self.action_solo_seguros,
         "ninguno": self.action_ninguno, "actualizar": self.action_actualizar,
         "cancelar": self.action_salir}[ev.button.id or "cancelar"]()

    def action_actualizar(self) -> None:
        self.dismiss("actualizar")

    def action_atras(self) -> None:
        self.dismiss("atras")

    def action_continuar(self) -> None:
        self.dismiss(self.seleccion())

    def action_salir(self) -> None:
        self.dismiss(None)
