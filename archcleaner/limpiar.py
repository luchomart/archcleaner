"""Piezas de `limpiar`: armar las tareas elegidas y los paneles del plan y del resultado.

El flujo interactivo (elegir → plan → confirmar → ejecutar) vive en la app: tui/flujos.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .acciones import LOG, Tarea, armar_tarea, procesos_abiertos
from .modelo import Hallazgo, Modo
from .util import humano


def armar_tareas(hallazgos: list[Hallazgo], seleccion: dict) -> list[Tarea]:
    por_numero = {h.numero: h for h in hallazgos}
    tareas = [armar_tarea(por_numero[n], elegidos) for n, elegidos in seleccion.items()]
    return [t for t in tareas if t.rutas or t.comandos]


def panel_definitivo(tareas: list[Tarea]) -> Panel:
    """La lista exacta de lo que se borraría para siempre."""
    lista = Table(box=None, show_header=False, padding=(0, 1))
    lista.add_column(justify="right", style="red", width=9)
    lista.add_column(overflow="fold")
    home = str(Path.home())
    for t in tareas:
        for r in t.rutas:
            ruta = str(r)
            lista.add_row(humano(t.peso_de(r)), "~" + ruta[len(home):] if ruta.startswith(home + "/") else ruta)
    return Panel(lista, title=f"[bold red]⚠ Se borra PARA SIEMPRE ({humano(sum(t.peso for t in tareas))})[/]",
                 title_align="left", border_style="red", box=box.HEAVY, padding=(0, 1))


def panel_plan(tareas: list[Tarea]) -> Panel:
    t = Table(box=box.SIMPLE_HEAD, expand=True, header_style="bold dim")
    t.add_column("", width=2)
    t.add_column("Qué", ratio=1)
    t.add_column("Peso", justify="right", width=9)
    t.add_column("Cómo", ratio=1)
    avisos: dict[str, str] = {}  # texto -> estilo (sin repetidos)
    ahora = papelera = 0
    for tarea in tareas:
        h, lim = tarea.hallazgo, tarea.hallazgo.limpieza
        assert lim
        como = Text(lim.describir())
        if lim.sudo:
            como.append(" [SUDO]", style="bold magenta")
        elegidos = len(tarea.rutas) + (len(tarea.comandos) if lim.por_item else 0)
        cuantos = f"  ({elegidos} de {sum(1 for i in h.detalle if i.elegible)})" if lim.por_item else ""
        t.add_row(h.nivel.icono, Text.assemble(h.titulo, (cuantos, "dim")), humano(tarea.peso), como)
        if tarea.modo == Modo.PAPELERA:
            papelera += tarea.peso
        else:
            ahora += tarea.peso
        if lim.nota:
            avisos[f"⚠ {h.titulo}: {lim.nota}"] = "yellow"
        if abiertos := procesos_abiertos(lim.cerrar):
            avisos[f"⚠ {', '.join(abiertos)} está abierto: cerralo o «{h.titulo}» se va a saltear."] = "bold yellow"

    totales = Text.assemble(
        ("Se libera ahora: ", "bold"), (humano(ahora) + "     ", "bold green"),
        ("Va a la papelera: ", "bold"), (humano(papelera), "bold yellow"),
        (" (se libera cuando la vacíes)", "dim") if papelera else "",
    )
    partes: list = [t, totales]
    if avisos:
        partes += [Text(""), *(Text(t, style=e) for t, e in avisos.items())]
    return Panel(Group(*partes), title="[bold]📝 Plan de limpieza[/]", title_align="left",
                 border_style="cyan", box=box.ROUNDED, padding=(0, 1))


def _puntos_montaje(tareas: list[Tarea]) -> set[str]:
    puntos = {"/"}
    for t in tareas:
        for r in t.rutas:
            p = os.path.realpath(r)
            while not os.path.ismount(p):
                p = os.path.dirname(p)
            puntos.add(p)
    return puntos


def libre(tareas: list[Tarea]) -> dict[str, int]:
    return {p: shutil.disk_usage(p).free for p in _puntos_montaje(tareas)}


def panel_final(tareas: list[Tarea], resultados: list, antes: dict[str, int]) -> Panel:
    t = Table(box=None, padding=(0, 2))
    t.add_column("Disco", style="bold")
    t.add_column("Liberado", justify="right", style="bold green")
    t.add_column("Libre ahora", justify="right")
    for p, libre_antes in sorted(antes.items()):
        libre = shutil.disk_usage(p).free
        t.add_row(p, humano(max(0, libre - libre_antes)), humano(libre))
    ok = sum(r.ok for r in resultados)
    resumen = Text.assemble(
        (f"{ok} de {len(resultados)} tareas completas", "bold green" if ok == len(resultados) else "bold yellow"),
        ("   ·   registro en ", "dim"), (str(LOG), "dim"),
    )
    partes: list = [t, Text(""), resumen]
    if any(t.modo == Modo.PAPELERA for t in tareas):
        partes.append(Text("Lo que fue a la papelera se puede recuperar desde la papelera de tu gestor de archivos.", style="dim"))
    return Panel(Group(*partes), title="[bold]✅ Listo[/]", title_align="left", border_style="green",
                 box=box.ROUNDED, padding=(0, 1))
