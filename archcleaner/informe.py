"""Cómo se muestra el análisis en la terminal (rich).

Orden del informe:
  1. Encabezado
  2. Discos + resumen (lado a lado)
  3. Índice numerado de todos los hallazgos
  4. Una tarjeta por hallazgo con el detalle
  5. Árbol del peso de cada disco
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .analisis import Resultado
from .escaner import Nodo, arbol
from .modelo import Hallazgo, Modo, Nivel
from .util import humano

MAX_DETALLE = 6
CARPETA_INFORMES = Path.home() / ".local/state/archcleaner/informes"

ICONO_MODO = {
    Modo.BORRAR: ("borrar", "green"),
    Modo.VACIAR: ("vaciar", "green"),
    Modo.PAPELERA: ("papelera", "yellow"),
    Modo.COMANDO: ("comando", "cyan"),
}


def barra(fraccion: float, ancho: int = 20, color: str = "cyan") -> Text:
    fraccion = max(0.0, min(1.0, fraccion))
    llenos = round(fraccion * ancho)
    return Text("━" * llenos, style=color) + Text("━" * (ancho - llenos), style="grey23")


def _color_uso(fraccion: float) -> str:
    return "red" if fraccion >= 0.9 else "yellow" if fraccion >= 0.75 else "green"


class _Juntar:
    """Imita a Console.print pero guarda las piezas (para mostrarlas dentro de la app)."""

    def __init__(self) -> None:
        self.partes: list = []

    def print(self, *objetos) -> None:
        self.partes.extend(objetos or [Text("")])


def componer(res: Resultado, pie: bool = True, comparacion=None) -> list:
    j = _Juntar()
    _escribir(res, j, pie, comparacion)  # type: ignore[arg-type]
    return j.partes


def mostrar(res: Resultado, consola: Console, comparacion=None) -> None:
    _escribir(res, consola, pie=True, comparacion=comparacion)


def _escribir(res: Resultado, consola: Console, pie: bool, comparacion=None) -> None:
    consola.print()
    consola.print(_encabezado())
    consola.print(_tablero(res))
    if comparacion is not None:
        from .historial import panel_resumen
        consola.print(panel_resumen(comparacion))
    consola.print(_indice(res))
    _tarjetas(res, consola)
    _arboles(res, consola)
    _avisos(res, consola)
    if not pie:
        return
    consola.print()
    consola.print(Rule(style="grey35"))
    consola.print(Text.assemble(
        ("  Para limpiar: ", "dim"), ("archcleaner limpiar", "bold cyan"),
        ("   ·   los 🟢 vienen tildados, los 🟡 los elegís vos", "dim"),
    ))


# ── 1. Encabezado ─────────────────────────────────────────────────────────────

def _encabezado() -> Panel:
    titulo = Text.assemble(
        ("🧹  ARCHCLEANER", "bold cyan"), (" by luchomart", "italic #af87ff"), ("   análisis de disco", "bold"),
        ("   ·   " + datetime.now().strftime("%d/%m/%Y %H:%M"), "dim"),
    )
    sub = Text("Modo solo lectura: no se borró nada.", style="green")
    return Panel(Group(titulo, sub), box=box.HEAVY, border_style="cyan", padding=(0, 2))


# ── 2. Discos + resumen ───────────────────────────────────────────────────────

def _tablero(res: Resultado) -> Table:
    grilla = Table.grid(expand=True, padding=(0, 1))
    grilla.add_column(ratio=3)
    grilla.add_column(ratio=2)
    grilla.add_row(_discos(res), _resumen(res))
    return grilla


def _discos(res: Resultado) -> Panel:
    puntos = ["/"] + [e.raiz for e in res.ctx.escaneos if os.path.ismount(e.raiz) and e.raiz != "/"]
    t = Table(box=None, padding=(0, 1), expand=True, show_edge=False)
    t.add_column("Disco", style="bold")
    t.add_column("Uso", ratio=1)
    t.add_column("Libre", justify="right")
    for p in dict.fromkeys(puntos):
        try:
            u = shutil.disk_usage(p)
        except OSError:
            continue
        f = u.used / u.total if u.total else 0
        uso = barra(f, 16, _color_uso(f)) + Text(f" {f:.0%}", style=_color_uso(f))
        t.add_row(p, uso, Text.assemble((humano(u.free), "bold"), (f" de {humano(u.total)}", "dim")))
    return Panel(t, title="[bold]💽 Discos[/]", title_align="left", border_style="grey50", box=box.ROUNDED)


def _total(res: Resultado, nivel: Nivel) -> int:
    return sum(h.peso or 0 for h in res.hallazgos if h.nivel == nivel and h.suma)


def _resumen(res: Resultado) -> Panel:
    t = Table.grid(padding=(0, 1))
    t.add_column()
    t.add_column(justify="right")
    t.add_row(Text("🟢 Sin riesgo", style="green"), Text(humano(_total(res, Nivel.SEGURO)), style="bold green"))
    t.add_row(Text("🟡 Si revisás", style="yellow"), Text(humano(_total(res, Nivel.REVISAR)), style="bold yellow"))
    t.add_row(Text("(gigantes y Workshop aparte)", style="dim"), "")
    return Panel(t, title="[bold]✨ Podés liberar[/]", title_align="left", border_style="grey50", box=box.ROUNDED)


# ── 3. Índice ─────────────────────────────────────────────────────────────────

def _indice(res: Resultado) -> Panel:
    t = Table(box=box.SIMPLE_HEAD, expand=True, padding=(0, 1), header_style="bold dim")
    t.add_column("#", justify="right", style="dim", width=3)
    t.add_column("", width=2)
    t.add_column("Peso", justify="right", width=9)
    t.add_column("Qué es", ratio=1, overflow="ellipsis", no_wrap=True)
    t.add_column("Categoría", style="dim", width=11)
    t.add_column("Cómo", width=13)

    niveles = [n for n in Nivel if any(h.nivel == n for h in res.hallazgos)]
    for nivel in niveles:
        grupo = [h for h in res.hallazgos if h.nivel == nivel]
        for i, h in enumerate(grupo):
            peso = Text(humano(h.peso) + ("+" if h.incompleto else ""), style=f"bold {nivel.color}")
            if not h.suma:
                peso.stylize("italic")
            t.add_row(str(h.numero), nivel.icono, peso, h.titulo, h.categoria, _como(h),
                      end_section=(i == len(grupo) - 1 and nivel != niveles[-1]))
    return Panel(t, title="[bold]📋 Qué encontré[/]", title_align="left", border_style="grey50", box=box.ROUNDED)


def _como(h: Hallazgo) -> Text:
    if not h.limpieza:
        return Text("—", style="dim")
    nombre, color = ICONO_MODO[h.limpieza.modo]
    txt = Text(nombre, style=color)
    if h.limpieza.sudo:
        txt.append(" sudo", style="bold magenta")
    return txt


# ── 4. Tarjetas ───────────────────────────────────────────────────────────────

def _tarjetas(res: Resultado, consola: Console) -> None:
    for nivel in Nivel:
        grupo = [h for h in res.hallazgos if h.nivel == nivel]
        if not grupo:
            continue
        consola.print()
        consola.print(Rule(Text(f" {nivel.icono}  {nivel.nombre.upper()} ", style=f"bold {nivel.color}"),
                           style=nivel.color, characters="─"))
        for h in grupo:
            consola.print(_tarjeta(h))


def _tarjeta(h: Hallazgo) -> Panel:
    partes: list = [Text(h.explicacion, style="grey70")]

    if h.detalle:
        t = Table(box=None, show_header=False, padding=(0, 1), pad_edge=False)
        t.add_column(justify="right", style="cyan", no_wrap=True, width=9)
        t.add_column(overflow="fold")
        for item in h.detalle[:MAX_DETALLE]:
            t.add_row(humano(item.peso), item.nombre)
        if len(h.detalle) > MAX_DETALLE:
            resto = h.detalle[MAX_DETALLE:]
            t.add_row(Text(humano(sum(i.peso or 0 for i in resto)), style="dim"),
                      Text(f"… y {len(resto)} más", style="dim"))
        partes += [Text(""), t]

    if h.limpieza:
        linea = Text.assemble(("\n▸ ", h.nivel.color), ("Cómo se limpia: ", "bold"), h.limpieza.describir())
        if h.limpieza.sudo:
            linea.append("  [SUDO]", style="bold magenta")
        if h.limpieza.cerrar:
            linea.append(f"  (con {', '.join(h.limpieza.cerrar)} cerrado)", style="dim")
        partes.append(linea)
    if h.incompleto:
        partes.append(Text("+ hay carpetas sin permiso de lectura: puede pesar más.", style="dim italic"))

    titulo = Text.assemble((f" #{h.numero} ", "bold reverse " + h.nivel.color), " ", (h.titulo, "bold"), " ")
    subtitulo = Text.assemble((f" {humano(h.peso)} ", f"bold {h.nivel.color}"), (f"· {h.categoria} ", "dim"))
    return Panel(Group(*partes), title=titulo, title_align="left", subtitle=subtitulo, subtitle_align="right",
                 border_style=h.nivel.color, box=box.ROUNDED, padding=(0, 2))


# ── 5. Árboles ────────────────────────────────────────────────────────────────

def _arboles(res: Resultado, consola: Console) -> None:
    if not res.ctx.escaneos:
        return
    consola.print()
    consola.print(Rule(Text(" 📂  DÓNDE ESTÁ EL PESO ", style="bold cyan"), style="cyan"))
    consola.print(Text("  Carpetas de más de 1 GB, de mayor a menor. Las barras son relativas al total del disco.",
                       style="dim"))
    home = str(res.ctx.home)
    for esc in res.ctx.escaneos:
        if not esc.peso:
            continue
        raiz = arbol(esc, profundidad=4, max_hijos=6)
        nombre = "~ (tu home)" if raiz.ruta == home else "/ (sistema, sin tu home)" if raiz.ruta == "/" else raiz.ruta
        t = Tree(Text.assemble((nombre, "bold cyan"), ("  " + humano(raiz.peso), "bold")), guide_style="grey35")
        _ramas(t, raiz, raiz.peso, res)
        partes: list = [t]
        if esc.sin_permiso:
            partes.append(Text(f"{len(esc.sin_permiso)} carpetas sin permiso de lectura no se pudieron medir.",
                               style="dim italic"))
        consola.print(Panel(Group(*partes), border_style="grey35", box=box.ROUNDED, padding=(0, 1)))


def _ramas(t: Tree, nodo: Nodo, total: int, res: Resultado) -> None:
    for h in nodo.hijos:
        linea = Text.assemble((f"{humano(h.peso):>9} ", "bold"), barra(h.peso / total, 10), "  ", h.etiqueta)
        if etiqueta := res.ctx.etiquetas.get(h.ruta):
            linea.append(f"  ← {etiqueta}", style="magenta")
        _ramas(t.add(linea), h, total, res)


def _avisos(res: Resultado, consola: Console) -> None:
    if not res.ctx.avisos:
        return
    consola.print(Panel(Text("\n".join(res.ctx.avisos), style="yellow"), title="⚠ Avisos",
                        border_style="yellow", box=box.ROUNDED))


def guardar(consola: Console) -> Path:
    CARPETA_INFORMES.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA_INFORMES / f"informe-{datetime.now():%Y-%m-%d-%H%M}.txt"
    ruta.write_text(consola.export_text())
    (CARPETA_INFORMES / "informe-actual.txt").write_text(ruta.read_text())
    return ruta
