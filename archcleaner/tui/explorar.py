"""📂 Explorar: navegar carpetas ordenadas por peso, con lo que ArchCleaner sabe de cada cosa.

Los pesos de las carpetas salen del último análisis (no se vuelve a medir el disco al navegar);
los archivos se leen al entrar a cada carpeta. Se puede mandar a la papelera o borrar, siempre
pasando por seguridad.py; lo del sistema (fuera de tu home y de los discos de datos) es solo para mirar.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from ..acciones import armar_tarea, ejecutar
from ..analisis import Resultado
from ..escaner import escanear
from ..limpiar import panel_definitivo
from ..modelo import Hallazgo, Limpieza, Modo, Nivel
from ..seguridad import ZONAS_DISCOS, Verificador
from ..util import acortar, dentro_de, humano
from ..estado import hace, leer
from ..historial import Foto
from .comunes import ESPACIO, ConfirmarBorrado, Dialogo, barra_botones, cabecera


MINIMO_FILA = 10 * 1024**2  # cambios más chicos no se marcan en la lista


@dataclass
class Entrada:
    ruta: str
    nombre: str
    carpeta: bool
    peso: int | None
    modificado: float
    enlace: bool = False


class ExplorarScreen(Screen[None]):
    BINDINGS = [
        Binding("backspace", "subir", "Subir"),
        Binding("delete", "papelera", "Papelera"),
        Binding("shift+delete", "borrar", "Borrar"),
        Binding("f5,r", "actualizar", "Actualizar"),
        Binding("o", "abrir", "Abrir en el gestor de archivos"),
        Binding("escape", "cerrar", "Inicio"),
    ]

    def __init__(self, res: Resultado, inicio: str, anterior: Foto | None = None):
        super().__init__()
        self.res = res
        self.anterior = anterior  # foto del análisis anterior: para mostrar cuánto creció cada carpeta
        self.raiz = inicio
        self.actual = inicio
        self.entradas: list[Entrada] = []
        self.adelante: list[str] = []  # carpetas de las que saliste con «atrás» (para volver con «adelante»)
        self.verif = Verificador()
        self.home = str(Path.home())
        self.marcas = self._marcas(res.hallazgos)

    # ── datos ──

    @staticmethod
    def _marcas(hallazgos: list[Hallazgo]) -> dict[str, Hallazgo]:
        """ruta -> hallazgo (🟢/🟡) que la menciona, para marcarla en la lista."""
        res: dict[str, Hallazgo] = {}
        for h in hallazgos:
            if h.nivel == Nivel.INFO:
                continue
            for r in [*h.rutas, *(i.ruta for i in h.detalle if i.ruta)]:
                res.setdefault(os.path.realpath(r), h)
        return res

    def peso_carpeta(self, ruta: str) -> int | None:
        for esc in self.res.ctx.escaneos:
            if ruta in esc.total and esc.contiene(ruta):
                return esc.total[ruta]
        return None

    def _leer(self, carpeta: str) -> list[Entrada]:
        res = []
        try:
            it = list(os.scandir(carpeta))
        except OSError as e:
            self.notify(f"No se puede leer {carpeta}: {e.strerror}", severity="warning")
            return res
        for e in it:
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            es_dir = stat.S_ISDIR(st.st_mode)
            peso = self.peso_carpeta(e.path) if es_dir else st.st_blocks * 512
            res.append(Entrada(e.path, e.name, es_dir, peso, st.st_mtime, stat.S_ISLNK(st.st_mode)))
        return sorted(res, key=lambda x: (x.peso is None, -(x.peso or 0), x.nombre.lower()))

    # ── armado ──

    def compose(self) -> ComposeResult:
        yield cabecera("📂 Explorar", "clic/enter entrar · ⌫ subir · Supr papelera · Shift+Supr borrar · "
                                     "o abrir carpeta · F5 medir")
        with Horizontal(classes="migas"):
            yield Static(id="ruta", classes="ruta")
            yield Static(id="resumen", classes="resumen")
        with Vertical():
            yield OptionList(id="lista", classes="lista")
            yield Static(id="info", classes="info")
        # Tres grupos: navegar · borrar · app
        with Horizontal(classes="botones barra-explorar"):
            yield Button("← Subir", id="subir")
            yield Button("📂 Abrir", id="abrir")
            yield Static(classes="separador")
            yield Button("🗑 Papelera", id="papelera", variant="warning")
            yield Button("🔥 Borrar", id="borrar", variant="error")
            yield Static(classes="espacio")
            yield Button("🔄 Actualizar", id="actualizar")
            yield Button("🏠 Inicio", id="cerrar", variant="primary")

    def on_mount(self) -> None:
        self._ir(self.actual)
        self.query_one(OptionList).focus()

    def _ir(self, carpeta: str, resaltar: str | None = None) -> None:
        self.actual = carpeta
        self.entradas = self._leer(carpeta)
        total = self.peso_carpeta(carpeta) or sum(e.peso or 0 for e in self.entradas) or 1
        lista = self.query_one(OptionList)
        lista.set_options([Option(self._fila(e, total), id=str(i)) for i, e in enumerate(self.entradas)])
        if self.entradas:
            idx = next((i for i, e in enumerate(self.entradas) if e.ruta == resaltar), 0)
            lista.highlighted = idx
        else:
            self.query_one("#info", Static).update(Text("(carpeta vacía)", style="dim"))
        self._migas()

    def _fila(self, e: Entrada, total: int) -> Text:
        frac = (e.peso or 0) / total
        llenos = round(min(1.0, frac) * 16)
        color = "red" if frac >= 0.5 else "yellow" if frac >= 0.2 else "cyan"
        fila = Text.assemble(
            (f"{humano(e.peso) if e.peso is not None else '—':>9} ", "bold"),
            ("━" * llenos, color), ("━" * (16 - llenos), "grey23"),
            (f" {frac:>4.0%}  ", "dim"),
            *self._cambio(e),
            ("📁 " if e.carpeta else "🔗 " if e.enlace else "📄 ", ""),
            (acortar(e.nombre, 48), "bold" if e.carpeta else ""),
        )
        real = os.path.realpath(e.ruta)
        if h := self.marcas.get(real):
            fila.append(f"  {h.nivel.icono} {h.titulo}", style=h.nivel.color)
        elif etiqueta := self.res.ctx.etiquetas.get(real):
            fila.append(f"  ← {etiqueta}", style="magenta")
        return fila

    def _antes(self, e: Entrada) -> int | None:
        """Lo que pesaba en el análisis anterior (0 si no estaba; None si no se sabe)."""
        if not self.anterior or not e.carpeta or e.peso is None:
            return None
        viejas = self.anterior.carpetas
        if e.ruta in viejas:
            return viejas[e.ruta]
        return 0 if os.path.dirname(e.ruta) in viejas else None

    def _cambio(self, e: Entrada) -> list[tuple[str, str]]:
        """Columna «▲ 1.2 GB» (creció) / «▼ 300 MB» (se achicó), solo si hay un análisis anterior."""
        if not self.anterior:
            return []
        antes = self._antes(e)
        if antes is None or abs((e.peso or 0) - antes) < MINIMO_FILA:
            return [(" " * 11, "")]
        d = (e.peso or 0) - antes
        if antes == 0:
            return [(f"{'nueva':>9}  ", "magenta")]
        return [(f"{('▲ ' if d > 0 else '▼ ') + humano(abs(d)):>9}  ", "yellow" if d > 0 else "green")]

    def _migas(self) -> None:
        """La ruta como una línea: «📂 / › ~ › .local › share», cada parte clickeable."""
        partes = Path(self.actual).parts
        self.rutas_migas: list[str] = []
        trozos: list[str] = []
        for i in range(len(partes)):
            ruta = str(Path(*partes[: i + 1]))
            if dentro_de(self.home, ruta) and ruta not in (self.home, "/"):
                continue  # /home y /home/luciano se muestran como "~"
            texto = "~" if ruta == self.home else ("/" if ruta == "/" else partes[i])
            texto = texto.replace("[", "\\[")
            self.rutas_migas.append(ruta)
            n = len(self.rutas_migas) - 1
            estilo = "bold $accent" if ruta == self.actual else "$text-muted"
            trozos.append(f"[{estilo}][@click=screen.miga({n})]{texto}[/][/]")
        self.query_one("#ruta", Static).update("📂 " + " [dim]›[/] ".join(trozos))
        peso = self.peso_carpeta(self.actual)
        cantidad = len(self.entradas)
        self.query_one("#resumen", Static).update(Text.assemble(
            (f"{cantidad} elementos", "dim"), ("  ·  ", "dim"), (humano(peso) if peso else "", "bold")))

    def action_miga(self, n: int) -> None:
        self._ir(self.rutas_migas[n], resaltar=self.actual)

    def _elegida(self) -> Entrada | None:
        lista = self.query_one(OptionList)
        if lista.highlighted is None or not self.entradas:
            return None
        return self.entradas[lista.highlighted]

    def _solo_lectura(self, ruta: str) -> str | None:
        if not (dentro_de(ruta, self.home) or any(dentro_de(ruta, z) for z in ZONAS_DISCOS)):
            return "Fuera de tu home y de los discos de datos: acá solo se mira."
        return self.verif.problema(ruta)

    def on_option_list_option_highlighted(self, ev: OptionList.OptionHighlighted) -> None:
        e = self._elegida()
        if not e:
            return
        filas = [Text.assemble(("📁 " if e.carpeta else "📄 ", ""), (e.ruta.replace(self.home, "~", 1), "bold"))]
        detalle = Text.assemble(("Peso: ", "dim"), (humano(e.peso) if e.peso is not None else "sin medir", "bold"),
                                ("   ·   Modificado: ", "dim"),
                                (datetime.fromtimestamp(e.modificado).strftime("%d/%m/%Y %H:%M"), ""))
        filas.append(detalle)
        antes = self._antes(e)
        if antes is not None and self.anterior:
            d = (e.peso or 0) - antes
            cuando = f"En el análisis del {self.anterior.cuando}"
            filas.append(Text(f"{cuando} no estaba (o pesaba menos de 1 MB)." if antes == 0 else
                              f"{cuando} pesaba {humano(antes)}" + (f" ({'+' if d > 0 else '−'}{humano(abs(d))})"
                                                                     if abs(d) >= MINIMO_FILA else ", igual que ahora."),
                              style="yellow" if d >= MINIMO_FILA else "green" if d <= -MINIMO_FILA else "dim"))
        real = os.path.realpath(e.ruta)
        if h := self.marcas.get(real):
            filas.append(Text(f"{h.nivel.icono} {h.titulo}: {h.explicacion}", style=h.nivel.color))
        elif etiqueta := self.res.ctx.etiquetas.get(real):
            filas.append(Text(f"← {etiqueta}", style="magenta"))
        if motivo := self._solo_lectura(e.ruta):
            filas.append(Text(f"🔒 No se puede borrar desde acá: {motivo}", style="dim"))
        texto = Text("\n").join(filas)
        self.query_one("#info", Static).update(texto)

    # ── acciones ──

    def on_option_list_option_selected(self, ev: OptionList.OptionSelected) -> None:
        e = self._elegida()
        if e and e.carpeta and not e.enlace:
            self.adelante.clear()
            self._ir(e.ruta)

    def action_atras(self) -> None:
        if self.actual == "/":
            self.dismiss(None)
            return
        self.adelante.append(self.actual)
        self._ir(str(Path(self.actual).parent), resaltar=self.actual)

    def action_adelante(self) -> None:
        if self.adelante:
            self._ir(self.adelante.pop())

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        acciones = {"subir": self.action_subir, "abrir": self.action_abrir, "papelera": self.action_papelera,
                    "borrar": self.action_borrar, "actualizar": self.action_actualizar, "cerrar": self.action_cerrar}
        if ev.button.id in acciones:
            acciones[ev.button.id]()

    def action_subir(self) -> None:
        if self.actual != "/":
            self._ir(str(Path(self.actual).parent), resaltar=self.actual)

    def action_abrir(self) -> None:
        e = self._elegida()
        destino = e.ruta if e and e.carpeta else self.actual
        subprocess.Popen(["xdg-open", destino], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.notify(f"Abriendo {destino.replace(self.home, '~', 1)}")

    def action_papelera(self) -> None:
        self._borrar(Modo.PAPELERA)

    def action_borrar(self) -> None:
        self._borrar(Modo.BORRAR)

    @work
    async def _borrar(self, modo: Modo) -> None:
        e = self._elegida()
        if not e:
            return
        if motivo := self._solo_lectura(e.ruta):
            self.notify(motivo, title="🔒 No se puede", severity="warning")
            return
        h = Hallazgo("Explorar", e.nombre, Nivel.REVISAR, e.peso, "", rutas=[Path(e.ruta)],
                     detalle=[], limpieza=Limpieza(modo))
        tarea = armar_tarea(h)
        if modo == Modo.BORRAR:
            if not await self.app.push_screen_wait(ConfirmarBorrado(panel_definitivo([tarea]))):
                return
        else:
            r = await self.app.push_screen_wait(Dialogo(
                "🗑 Mandar a la papelera",
                Text.assemble(e.ruta.replace(self.home, "~", 1), (f"  ({humano(e.peso)})", "bold"),
                              ("\n\nSe puede recuperar desde la papelera de tu gestor de archivos. El espacio se libera al vaciarla.",
                               "dim")),
                [("si", "🗑 A la papelera", "warning"), ("no", "Cancelar", "default")]))
            if r != "si":
                return
        self.notify(f"{'Borrando' if modo == Modo.BORRAR else 'Mandando a la papelera'} {e.nombre}…")
        res = await _en_hilo(ejecutar, tarea, self.verif, lambda s: None)
        if res.ok:
            self._descontar(e)
            self.notify(f"✔ {e.nombre}: {res.mensaje}", title="Listo")
        else:
            self.notify("\n".join(res.errores[:3]) or res.mensaje, title="No se pudo", severity="error")
        idx = self.query_one(OptionList).highlighted or 0
        self._ir(self.actual)
        if self.entradas:
            self.query_one(OptionList).highlighted = min(idx, len(self.entradas) - 1)

    def _descontar(self, e: Entrada) -> None:
        """Ajusta los pesos guardados después de borrar algo (sin volver a medir todo)."""
        peso = e.peso or 0
        for esc in self.res.ctx.escaneos:
            if not esc.contiene(e.ruta):
                continue
            for d in [d for d in esc.total if dentro_de(d, e.ruta)]:
                del esc.total[d]
            padre = os.path.dirname(e.ruta)
            while padre in esc.total:
                esc.total[padre] -= peso
                if padre == esc.raiz:
                    break
                padre = os.path.dirname(padre)

    @work
    async def action_actualizar(self) -> None:
        """Vuelve a medir la carpeta actual (y corrige el peso de las de arriba)."""
        actual = self.actual
        esc = next((x for x in self.res.ctx.escaneos if x.contiene(actual) and actual in x.total), None)
        self.notify("Midiendo de nuevo…")
        nuevo = await _en_hilo(escanear, actual, tuple(esc.excluidas) if esc else ())
        if esc:
            delta = nuevo.peso - esc.total.get(actual, 0)
            for d in [d for d in esc.total if dentro_de(d, actual)]:
                del esc.total[d]
            esc.total.update(nuevo.total)
            padre = os.path.dirname(actual)
            while padre in esc.total and actual != esc.raiz:
                esc.total[padre] += delta
                if padre == esc.raiz:
                    break
                padre = os.path.dirname(padre)
        self._ir(actual, resaltar=(self._elegida().ruta if self._elegida() else None))
        self.notify("Actualizado.", title="🔄")

    def action_cerrar(self) -> None:
        self.dismiss(None)


async def _en_hilo(funcion, *args):
    import asyncio
    return await asyncio.to_thread(funcion, *args)


class ElegirRaiz(ModalScreen[str | None]):
    """¿Qué explorar? Un renglón por disco (con cuánto queda libre) o una ruta escrita a mano."""

    BINDINGS = [Binding("escape", "cancelar", "Cancelar")]

    def __init__(self, res: Resultado):
        super().__init__()
        self.home = str(res.ctx.home)
        self.raices = [e for e in res.ctx.escaneos if e.peso]

    def _fila(self, raiz: str, peso: int, angosta: bool) -> Text:
        if raiz == self.home:
            icono, nombre, donde = "🏠", "Tu home", "~"
        elif raiz == "/":
            icono, nombre, donde = "💻", "Sistema", "/  (sin tu home)"
        else:
            icono, nombre, donde = "💽", os.path.basename(raiz) or raiz, raiz
        fila = Text.assemble(f" {icono}  ", (f"{nombre:<9}", "bold"), (f"{humano(peso):>10}  ", "bold cyan"))
        if not angosta:  # en terminales angostas no entra la ruta: el nombre ya alcanza
            fila.append(f"{donde:<20}", style="grey62")
        try:
            u = shutil.disk_usage(raiz)
            f = u.used / u.total
            color = "red" if f >= 0.9 else "yellow" if f >= 0.75 else "green"
            llenos = round(f * 10)
            fila.append_text(Text.assemble(("" if angosta else "  disco ", "dim"),
                                           ("━" * llenos, color), ("━" * (10 - llenos), "grey23"),
                                           (f" {f:.0%}", color), (f" · {humano(u.free)} libres", "dim")))
        except OSError:
            pass
        return fila

    def compose(self) -> ComposeResult:
        analisis = leer().get("analisis")
        cuando = hace(analisis["fecha"]) if analisis else "del último análisis"
        with Vertical(classes="dialogo elegir-raiz"):
            yield Static(Text("📂 ¿Qué querés explorar?", style="bold"), classes="dialogo-titulo")
            angosta = self.app.size.width < 100
            yield OptionList(*[Option(self._fila(e.raiz, e.peso, angosta), id=str(i))
                               for i, e in enumerate(self.raices)], id="raices")
            yield Static(Text(f"Pesos medidos {cuando} · adentro, 🔄 Actualizar vuelve a medir", style="dim"))
            yield Input(placeholder="…o escribí una carpeta (ej. ~/Descargas) y enter", id="ruta-manual")
            yield barra_botones([ESPACIO, ("cancelar", "Cancelar", "default")])

    def on_mount(self) -> None:
        self.query_one("#raices", OptionList).focus()

    def on_option_list_option_selected(self, ev: OptionList.OptionSelected) -> None:
        self.dismiss(self.raices[int(ev.option.id or 0)].raiz)

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ruta = os.path.realpath(os.path.expanduser(ev.value.strip()))
        if not ev.value.strip():
            return
        if not os.path.isdir(ruta):
            self.notify(f"No existe la carpeta {ruta}", severity="error")
            return
        self.dismiss(ruta)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(None)

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def action_atras(self) -> None:
        self.dismiss(None)
