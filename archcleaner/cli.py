"""Comandos de la terminal."""

from __future__ import annotations

import argparse
import os
import sys

from rich.console import Console

from . import __version__

# (nombre en español, nombre en inglés): los dos funcionan siempre; la ayuda muestra el del idioma actual.
COMANDOS = {
    "analizar": "analyze", "limpiar": "clean", "desinstalar": "uninstall", "explorar": "explore", "crecio": "grew",
}


def _idioma_pedido(argv: list[str]) -> str | None:
    """`--lang en` / `--lang=en` se mira antes que nada: los textos de la ayuda ya dependen del idioma."""
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--lang="):
            return a.split("=", 1)[1]
    return None


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    from . import i18n
    if pedido := _idioma_pedido(argv):
        i18n.elegir(pedido)
    from .i18n import tr

    en = i18n.idioma == "en"

    def comando(sub, es: str, ayuda: str):
        nombre, alias = (COMANDOS[es], es) if en else (es, COMANDOS[es])
        return sub.add_parser(nombre, aliases=[alias], help=ayuda)

    def opcion(p, es: str, en_: str, **kw):
        p.add_argument(*((en_, es) if en else (es, en_)), dest=es.lstrip("-").replace("-", "_"), **kw)

    parser = argparse.ArgumentParser(
        prog="archcleaner",
        description=tr("Analizador y limpiador de disco para Arch Linux. Por defecto no borra nada."),
    )
    parser.add_argument("--version", action="version", version=f"ArchCleaner {__version__}")
    parser.add_argument("--lang", choices=i18n.IDIOMAS, help=tr("idioma de la interfaz (por defecto, el del sistema)"))
    sub = parser.add_subparsers(dest="comando", metavar="COMANDO" if not en else "COMMAND")

    p = comando(sub, "analizar", tr("informe de qué ocupa espacio y qué se puede limpiar (solo lectura)"))
    opcion(p, "--rapido", "--quick", action="store_true",
           help=tr("no recorre los discos enteros: solo las fuentes de basura conocidas"))
    opcion(p, "--no-guardar", "--no-save", action="store_true",
           help=tr("no guarda el informe en ~/.local/state/archcleaner"))

    p = comando(sub, "limpiar", tr("elegir qué borrar (con resumen y confirmación antes de tocar nada)"))
    opcion(p, "--simulacro", "--dry-run", action="store_true", help=tr("muestra qué se haría, sin borrar nada"))

    p = comando(sub, "desinstalar", tr("desinstalar un programa sin dejar rastro (con ficha, plan y confirmación)"))
    p.add_argument("programa", nargs="?", metavar=tr("programa"),
                   help=tr("nombre del programa (si no, se elige de una lista)"))
    opcion(p, "--simulacro", "--dry-run", action="store_true", help=tr("muestra la ficha y el plan, sin tocar nada"))

    p = comando(sub, "explorar", tr("navegar carpetas ordenadas por peso (con la app)"))
    p.add_argument("programa", nargs="?", metavar=tr("carpeta"),
                   help=tr("carpeta donde empezar (si no, se elige el disco)"))

    p = comando(sub, "crecio", tr("qué creció y qué se achicó desde un análisis anterior (solo lectura)"))
    opcion(p, "--dias", "--days", type=float,
           help=tr("comparar con el análisis de hace N días (si no, con el anterior)"))

    args = parser.parse_args(argv)
    # el comando, siempre con su nombre en español (el que usa el resto del código)
    args.comando = {v: k for k, v in COMANDOS.items()}.get(args.comando, args.comando)
    if args.comando is None and not sys.stdout.isatty():
        parser.print_help()
        return 0
    if os.geteuid() == 0:
        print(tr("No corras ArchCleaner como root: corre como tu usuario y pide sudo solo cuando lo necesita."))
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
    from .estado import guardar_analisis, guardar_tiempos, tiempos_previos
    from .i18n import tr
    from .informe import guardar, mostrar
    from .util import acortar

    consola = Console(record=True)
    barra = Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"), BarColumn(bar_width=24),
                     TaskProgressColumn(), TimeRemainingColumn(), TextColumn("[dim]{task.fields[detalle]}"),
                     console=consola, transient=True)
    with barra:
        tarea = barra.add_task(tr("Arrancando…"), total=1.0, detalle="")

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
        consola.print("\n[dim]" + tr("Informe guardado en {ruta}", ruta=ruta) + "[/dim]")
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
