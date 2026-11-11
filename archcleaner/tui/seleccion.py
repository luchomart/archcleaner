"""Pantalla para tildar qué limpiar (o qué restos borrar). No borra nada: devuelve la selección.

Se usa con teclado (espacio, s, n, enter) o con el mouse: clic en una fila la elige (para ver su info,
🤖 o 🙈) y clic en su cajita [ ] la tilda/destilda.
También: ? = 🤖 qué es esto (IA local, si hay Ollama) · i = 🙈 no mostrar más (ver ignorados.py).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual import events
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from .. import ia, ignorados
from ..modelo import Hallazgo, Item, Nivel
from ..util import acortar, humano
from .ocultos import Ocultos, confirmar_ocultar
from .que_es import QueEsEsto, datos_de
from ..i18n import tr

# Selección: número de hallazgo -> None (el hallazgo entero) o lista de índices del detalle.
Seleccion = dict[int, list[int] | None]


class Lista(OptionList):
    """Como OptionList, pero un clic solo elige la fila: tildar es cosa de la cajita (ver SeleccionScreen)."""

    class Clic(Message):
        def __init__(self, indice: int, x: int) -> None:
            super().__init__()
            self.indice, self.x = indice, x

    async def _on_click(self, event: events.Click) -> None:
        indice: int | None = event.style.meta.get("option")
        if indice is None or self._options[indice].disabled:
            return
        self.highlighted = indice
        offset = event.get_content_offset(self)
        self.post_message(self.Clic(indice, offset.x if offset else -1))


# Columnas (dentro de la fila) donde está la cajita [ ]: en la fila de un grupo y en la de un ítem.
CAJA_GRUPO = range(4)
CAJA_ITEM = range(5, 10)


@dataclass
class Fila:
    hallazgo: Hallazgo
    item: int | None = None  # índice en hallazgo.detalle; None = fila del hallazgo


class SeleccionScreen(Screen[Seleccion | str | None]):
    """Devuelve la selección, None si se cancela, o "actualizar" para volver a buscar."""

    BINDINGS = [
        Binding("space", "tildar", tr("Tildar")),
        Binding("s", "solo_seguros", tr("Solo 🟢")),
        Binding("n", "ninguno", tr("Ninguno")),
        Binding("enter", "continuar", tr("Continuar"), priority=True),
        Binding("escape", "salir", tr("Cancelar")),
        Binding("r,f5", "actualizar", tr("Actualizar")),
        Binding("question_mark", "que_es", tr("¿Qué es esto? (IA local)")),
        Binding("i", "ocultar", tr("No mostrar más")),
    ]

    def __init__(self, hallazgos: list[Hallazgo], titulo: str = tr("🧹 Elegí qué limpiar"),
                 secciones: dict[Nivel, str] | None = None, previa: Seleccion | None = None, contexto: str = ""):
        """`contexto`: para la IA, qué es esta lista (ej. "restos del programa X"); en inglés, no se muestra."""
        super().__init__()
        self.titulo = titulo
        self.contexto = contexto
        self.secciones = secciones or {n: n.nombre for n in Nivel}
        self.origen = hallazgos  # la lista del análisis: al ocultar algo se corrige ahí también
        self.hallazgos = [h for h in hallazgos if h.limpieza]
        self.con_ia = False
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
            yield Lista(id="lista", classes="lista")
            yield Static(id="info", classes="info")
        with Horizontal(classes="botones barra-seleccion"):
            yield Button(tr("Continuar ▸"), id="continuar", variant="success")
            yield Button(tr("Solo 🟢"), id="seguros")
            yield Button(tr("Ninguno"), id="ninguno")
            yield Button(tr("🤖 ¿Qué es?"), id="que_es", classes="oculto")
            yield Button(tr("🙈 No mostrar"), id="ocultar")
            yield Static(classes="espacio")
            yield Button("", id="ocultos")
            yield Button(tr("🔄 Actualizar"), id="actualizar")
            yield Button(tr("Cancelar"), id="cancelar")

    def on_mount(self) -> None:
        self._redibujar()
        lista = self.query_one(OptionList)
        lista.focus()
        lista.highlighted = next((i for i, o in enumerate(lista.options) if not o.disabled), None)
        self._boton_ocultos()
        self._buscar_ia()

    @work
    async def _buscar_ia(self) -> None:
        if await asyncio.to_thread(ia.disponible):
            self.con_ia = True
            self.query_one("#que_es", Button).remove_class("oculto")
            self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        return self.con_ia if action == "que_es" else True

    def _boton_ocultos(self) -> None:
        n = len(ignorados.lista())
        boton = self.query_one("#ocultos", Button)
        boton.label = tr("🙈 Ocultos ({n})", n=n)
        boton.set_class(not n, "oculto")

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
            ("   ·   ", "dim"), (tr("{n} grupos", n=len(sel)), "bold"),
            ("   ·   ", "dim"), (tr("seleccionado: "), "dim"), (humano(self.total()), "bold green"),
            (tr("\nNada se borra todavía: después vas a ver el plan y confirmar.   "), "dim"),
            (tr("clic: "), "bold"), (tr("elegir"), "dim"), ("  ·  ", "dim"),
            (tr("[ ] o espacio: "), "bold"), (tr("tildar"), "dim"),
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
            texto.append(tr("   (con {programas} cerrado)", programas=", ".join(lim.cerrar)), style="yellow")
        if lim.nota:
            texto.append(f"\n⚠ {lim.nota}", style="yellow")
        info.update(texto)

    # ── acciones ──

    def on_lista_clic(self, ev: Lista.Clic) -> None:
        """Un clic ya eligió la fila; si cayó sobre la cajita, además la tilda/destilda."""
        fila = self.filas.get(self.query_one(Lista).get_option_at_index(ev.indice).id or "")
        if fila and ev.x in (CAJA_GRUPO if fila.item is None else CAJA_ITEM):
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
         "que_es": self.action_que_es, "ocultar": self.action_ocultar, "ocultos": self.action_ocultos,
         "cancelar": self.action_salir}[ev.button.id or "cancelar"]()

    # ── 🤖 qué es · 🙈 no mostrar más ──

    def _fila_resaltada(self) -> Fila | None:
        lista = self.query_one(OptionList)
        if lista.highlighted is None:
            return None
        return self.filas.get(lista.get_option_at_index(lista.highlighted).id or "")

    @staticmethod
    def _rutas_de(fila: Fila) -> tuple[list[Path], int | None]:
        """Las rutas que representa una fila (un ítem, o todo el grupo) y cuánto pesan."""
        h = fila.hallazgo
        if fila.item is not None:
            it = h.detalle[fila.item]
            return ([it.ruta] if it.ruta else []), it.peso
        if h.limpieza and h.limpieza.por_item:
            return [it.ruta for it in h.detalle if it.ruta], h.peso
        return list(h.rutas), h.peso

    def _peso_carpeta(self, ruta: str) -> int | None:
        res = getattr(self.app, "resultado", None)
        for esc in (res.ctx.escaneos if res else []):
            if ruta in esc.total and esc.contiene(ruta):
                return esc.total[ruta]
        return None

    def action_que_es(self) -> None:
        fila = self._fila_resaltada()
        if not fila or not self.con_ia:
            return
        rutas, peso = self._rutas_de(fila)
        if len(rutas) != 1:
            self.notify(tr("Elegí un ítem de la lista: la explicación del grupo ya está abajo."))
            return
        h = fila.hallazgo
        contexto = f"{h.titulo}: {h.explicacion}"  # lo que ArchCleaner ya sabe del grupo: ayuda a la IA
        if self.contexto:
            contexto += f" ({self.contexto})"
        self.app.push_screen(QueEsEsto(datos_de(rutas[0], peso, self._peso_carpeta, contexto)))

    @work
    async def action_ocultar(self) -> None:
        fila = self._fila_resaltada()
        if not fila:
            return
        rutas, peso = self._rutas_de(fila)
        if not rutas:
            self.notify(tr("Esto no se puede ocultar: no es una carpeta ni un archivo."), severity="warning")
            return
        if not await confirmar_ocultar(self.app, rutas, peso):
            return
        ignorados.ocultar(rutas, que=fila.hallazgo.titulo)
        # lo tildado apunta a índices del detalle, que cambian al sacar ítems: se reubica por identidad
        antes: list[tuple[Hallazgo, Item | None]] = [
            (x, x.detalle[int(i.rsplit("-", 1)[1])] if "-" in i else None)
            for x in self.hallazgos for i in self._ids_de(x) if i in self.marcados]
        ignorados.aplicar(self.origen)
        self.hallazgos = [x for x in self.origen if x.limpieza]
        self.marcados = set()
        for x, it in antes:
            if not any(y is x for y in self.hallazgos):
                continue
            if it is None:
                self.marcados.add(f"h{x.numero}")
            elif (k := next((k for k, y in enumerate(x.detalle) if y is it), None)) is not None:
                self.marcados.add(f"h{x.numero}-{k}")
        self._redibujar()
        self._boton_ocultos()
        self.notify(tr("No se va a proponer más. Lo podés volver a mostrar desde «🙈 Ocultos»."), title="🙈")

    @work
    async def action_ocultos(self) -> None:
        volver = await self.app.push_screen_wait(Ocultos())
        if volver:
            ignorados.mostrar(volver)
            self._boton_ocultos()
            self.notify(tr("Vuelve a aparecer en el próximo análisis: 🔄 Actualizar."), title="👁")

    def action_actualizar(self) -> None:
        self.dismiss("actualizar")

    def action_atras(self) -> None:
        self.dismiss("atras")

    def action_continuar(self) -> None:
        self.dismiss(self.seleccion())

    def action_salir(self) -> None:
        self.dismiss(None)
