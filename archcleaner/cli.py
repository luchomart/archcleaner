"""Comandos de la terminal."""

from __future__ import annotations

import argparse
import os
import sys

from rich.console import Console

from . import __version__

FASES_PENDIENTES: dict[str, str] = {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="archcleaner",
        description="Analizador y limpiador de disco para Arch Linux. Por defecto no borra nada.",
    )
    parser.add_argument("--version", action="version", version=f"ArchCleaner {__version__}")
    sub = parser.add_subparsers(dest="comando", metavar="COMANDO")

    p = sub.add_parser("analizar", help="informe de qué ocupa espacio y qué se puede limpiar (solo lectura)")
    p.add_argument("--rapido", action="store_true",
                   help="no recorre los discos enteros: solo las fuentes de basura conocidas")
    p.add_argument("--no-guardar", action="store_true", help="no guarda el informe en ~/.local/state/archcleaner")

    p = sub.add_parser("limpiar", help="elegir qué borrar (con resumen y confirmación antes de tocar nada)")
    p.add_argument("--simulacro", action="store_true", help="muestra qué se haría, sin borrar nada")

    p = sub.add_parser("desinstalar", help="desinstalar un programa sin dejar rastro (con ficha, plan y confirmación)")
    p.add_argument("programa", nargs="?", help="nombre del programa (si no, se elige de una lista)")
    p.add_argument("--simulacro", action="store_true", help="muestra la ficha y el plan, sin tocar nada")

    p = sub.add_parser("explorar", help="navegar carpetas ordenadas por peso (con la app)")
    p.add_argument("programa", nargs="?", metavar="carpeta", help="carpeta donde empezar (si no, se elige el disco)")

    p = sub.add_parser("crecio", help="qué creció y qué se achicó desde un análisis anterior (solo lectura)")
    p.add_argument("--dias", type=float, help="comparar con el análisis de hace N días (si no, con el anterior)")

    for nombre, fase in FASES_PENDIENTES.items():
        sub.add_parser(nombre, help=f"(todavía no: {fase})")

    args = parser.parse_args(argv)
    if args.comando is None and not sys.stdout.isatty():
        parser.print_help()
        return 0
    if args.comando in FASES_PENDIENTES:
        print(f"«{args.comando}» todavía no está hecho ({FASES_PENDIENTES[args.comando]}).")
        return 1
    if os.geteuid() == 0:
        print("No corras ArchCleaner como root: corre como tu usuario y pide sudo solo cuando lo necesita.")
        return 1
    if args.comando == "analizar":
        return _analizar(args)
    if args.comando == "crecio":
        return _crecio(args)

    # Todo lo interactivo es una sola app (teclado y mouse): menú, limpiar, desinstalar.
    from .tui.app import ArchCleanerApp
    ArchCleanerApp(
        inicio=args.comando or "menu",
        programa=getattr(args, "programa", None),
        simulacro=getattr(args, "simulacro", False),
    ).run()
    return 0


def _analizar(args: argparse.Namespace) -> int:
    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeRemainingColumn

    from .analisis import analizar
    from .util import acortar
    from .estado import guardar_analisis, guardar_tiempos, tiempos_previos
    from .informe import guardar, mostrar

    consola = Console(record=True)
    barra = Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"), BarColumn(bar_width=24),
                     TaskProgressColumn(), TimeRemainingColumn(), TextColumn("[dim]{task.fields[detalle]}"),
                     console=consola, transient=True)
    with barra:
        tarea = barra.add_task("Arrancando…", total=1.0, detalle="")

        def avance(fraccion: float, etapa: str, detalle: str) -> None:
            barra.update(tarea, completed=fraccion, description=etapa, detalle=acortar(detalle.rsplit("·", 1)[-1].strip(), 30))

        res = analizar(escanear_discos=not args.rapido, avance=avance, previos=tiempos_previos())
    guardar_tiempos(res.tiempos)
    comparacion = None
    if not args.rapido:
        from . import historial
        guardar_analisis(res.hallazgos)
        foto = historial.foto_de(res)
        if foto:
            historial.guardar(foto)
            if anterior := historial.anterior(foto.fecha):
                comparacion = historial.comparar(anterior, foto)
    mostrar(res, consola, comparacion)
    if not args.no_guardar:
        ruta = guardar(consola)
        consola.print(f"\n[dim]Informe guardado en {ruta}[/dim]")
    return 0


def _crecio(args: argparse.Namespace) -> int:
    from . import historial

    consola = Console()
    actual = historial.ultima()
    base = historial.anterior(actual.fecha, args.dias) if actual else None
    if not actual or not base:
        consola.print(historial.sin_historial(len(historial.listar()), en_app=False), style="yellow")
        return 1
    consola.print()
    consola.print(*historial.paneles(historial.comparar(base, actual)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
