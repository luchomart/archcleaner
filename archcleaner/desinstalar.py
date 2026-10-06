"""Piezas de `desinstalar`: buscar el programa, paneles de ficha/plan y la verificación final.

El flujo interactivo (elegir → ficha → restos → plan → ejecutar → verificar) vive en la app: tui/flujos.py
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import timeshift
from .acciones import Tarea
from .ficha import MUCHOS_PAQUETES, Ficha, _nombres_de_otros, _restos_home, _restos_sistema
from .modelo import Hallazgo, Item, Nivel
from .programas import Programa
from .util import ejecutar as correr
from .util import humano

SECCIONES = {Nivel.SEGURO: "Restos seguros", Nivel.REVISAR: "Restos probables", Nivel.INFO: "Info"}


def buscar(programas: list[Programa], busqueda: str | None) -> Programa | None:
    """El programa si la búsqueda coincide exacto con uno solo (por id o nombre)."""
    if not busqueda:
        return None
    b = busqueda.lower()
    exactos = [p for p in programas if b in (p.id.lower(), p.nombre.lower())]
    return exactos[0] if len(exactos) == 1 else None


def snapshot_sugerida(ficha: Ficha) -> bool | None:
    """None si no aplica (no es de pacman o no hay Timeshift); si no, si conviene por defecto."""
    if ficha.programa.origen not in ("repo", "aur") or not timeshift.disponible():
        return None
    return len(ficha.paquetes) > MUCHOS_PAQUETES


def manifiesto_steam(prog: Programa) -> Path:
    return Path(prog.extra["biblioteca"]) / "steamapps" / f"appmanifest_{prog.id}.acf"


def sigue_instalado(prog: Programa) -> bool:
    if prog.origen in ("repo", "aur"):
        return correr(["pacman", "-Q", prog.id]) is not None
    if prog.origen == "flatpak":
        return correr(["flatpak", "info", prog.id]) is not None
    if prog.origen == "steam":
        return manifiesto_steam(prog).exists()
    return os.path.exists(prog.id)


def libre() -> dict[str, int]:
    puntos = ["/"] + [os.path.join("/mnt", d) for d in os.listdir("/mnt") if os.path.ismount(os.path.join("/mnt", d))]
    return {p: shutil.disk_usage(p).free for p in puntos}


# ── Verificación ─────────────────────────────────────────────────────────────

@dataclass
class Verificacion:
    quedan: list[str] = field(default_factory=list)       # cosas que debían irse y siguen
    conservados: list[Item] = field(default_factory=list)  # restos que el usuario eligió no borrar
    nuevos: list[Hallazgo] = field(default_factory=list)   # restos que aparecieron después (ej. pacman dejó carpetas)
    liberado: int = 0

    @property
    def limpio(self) -> bool:
        return not self.quedan and not self.nuevos


def _clave(i: Item) -> str:
    return str(i.ruta or (i.comando or [""])[-1])


def verificar(ficha: Ficha, restos: list[Tarea], libre_antes: dict[str, int]) -> Verificacion:
    """Vuelve a buscar: ¿quedó el programa? ¿quedó algo de lo elegido? ¿apareció algo nuevo?"""
    prog = ficha.programa
    v = Verificacion()
    if prog.origen != "appimage" and sigue_instalado(prog):
        v.quedan.append(f"{prog.nombre} sigue instalado")
    for t in restos:
        v.quedan += [str(r) for r in t.rutas if os.path.lexists(r)]
        for cmd in t.comandos:
            v.quedan += [a for a in cmd[1:] if cmd[0] == "rm" and not a.startswith("-") and os.path.lexists(a)]

    ofrecidos = {_clave(i) for h in ficha.restos for i in h.detalle}
    nueva = Ficha(prog, paquetes=ficha.paquetes, claves=ficha.claves)
    otros = _nombres_de_otros(nueva)
    _restos_home(nueva, Path.home(), otros)
    if prog.origen in ("repo", "aur"):
        _restos_sistema(nueva, otros)
    v.conservados = [i for h in nueva.restos for i in h.detalle if _clave(i) in ofrecidos]
    for h in nueva.restos:
        h.detalle = [i for i in h.detalle if _clave(i) not in ofrecidos]
        if h.detalle:
            h.peso = sum(i.peso or 0 for i in h.detalle)
            v.nuevos.append(h)
    for i, h in enumerate(v.nuevos, 1):
        h.numero = i
    v.liberado = sum(max(0, shutil.disk_usage(p).free - libre) for p, libre in libre_antes.items())
    return v


# ── Paneles ──────────────────────────────────────────────────────────────────

def panel_ficha(ficha: Ficha) -> Panel:
    prog = ficha.programa
    origen, color = prog.etiqueta_origen
    cab = Text.assemble((f" {origen} ", f"bold {color} reverse"), "  ", (prog.nombre, "bold"),
                        (f"  {prog.version}" if prog.version else "", "dim"))
    partes: list = [cab]
    if prog.descripcion:
        partes.append(Text(prog.descripcion, style="grey70"))

    if ficha.paquetes and prog.origen in ("repo", "aur"):
        t = Table(box=None, show_header=False, padding=(0, 1), pad_edge=False)
        t.add_column(justify="right", style="cyan", width=9)
        t.add_column()
        for i in ficha.paquetes[:10]:
            t.add_row(humano(i.peso), i.nombre + ("" if i.nombre == prog.id else "  (dependencia que queda sin uso)"))
        if len(ficha.paquetes) > 10:
            t.add_row("", Text(f"… y {len(ficha.paquetes) - 10} más", style="dim"))
        partes += [Text(""), Text("📦 Se va con pacman:", style="bold"), t]

    if ficha.servicios:
        partes += [Text(""), Text("⚙️  Servicios que se apagan antes:", style="bold")]
        partes += [Text(f"   {s.unidad}" + (" (de usuario)" if s.usuario else "") + (" · activo ahora" if s.activo else ""))
                   for s in ficha.servicios]

    if ficha.restos:
        partes += [Text(""), Text("🧩 Restos que encontré:", style="bold")]
        for h in ficha.restos:
            partes.append(Text.assemble(f"   {h.nivel.icono} ", (f"{humano(h.peso):>9}  ", "bold"), h.titulo,
                                        (f"  ({len(h.detalle)})", "dim")))
    elif not ficha.bloqueo:
        partes += [Text(""), Text("🧩 No encontré restos fuera del paquete.", style="green")]

    for a in ficha.avisos:
        partes.append(Text(f"⚠ {a}", style="bold yellow"))
    if ficha.bloqueo:
        partes += [Text(""), Text(f"⛔ No se puede desinstalar: {ficha.bloqueo}", style="bold red")]
    else:
        partes += [Text(""), Text.assemble(("Liberarías hasta ", ""), (humano(ficha.peso_total), "bold green"))]
    return Panel(Group(*partes), title="[bold]📋 Ficha[/]", title_align="left",
                 border_style="red" if ficha.bloqueo else "cyan", box=box.ROUNDED, padding=(0, 1))


def panel_plan(ficha: Ficha, restos: list[Tarea]) -> Panel:
    prog = ficha.programa
    pasos: list[Text] = []
    for s in ficha.servicios:
        pasos.append(Text(f"apagar {s.unidad}" + ("" if s.usuario else "  [SUDO]")))
    if prog.origen in ("repo", "aur"):
        pasos.append(Text(f"pacman -Rns {prog.id}  [SUDO]  (quita {len(ficha.paquetes)} paquetes; pacman te pide confirmación)"))
    elif prog.origen == "flatpak":
        pasos.append(Text(f"flatpak uninstall --delete-data {prog.id}  + runtimes sin uso"))
    elif prog.origen == "steam":
        pasos.append(Text("Steam desinstala el juego (se abre su ventana)"))
    for t in restos:
        lim = t.hallazgo.limpieza
        assert lim
        n = len(t.rutas) + len(t.comandos)
        pasos.append(Text.assemble(f"{t.hallazgo.nivel.icono} {t.hallazgo.titulo} ", (f"({n})  ", "dim"),
                                   (humano(t.peso) + "  ", "bold"), (lim.describir(), "dim"),
                                   ("  [SUDO]" if lim.sudo else "", "magenta")))
    pasos.append(Text("🔎 verificar que no quede rastro"))
    filas = [Text.assemble((f"{i}. ", "dim"), p) for i, p in enumerate(pasos, 1)]
    return Panel(Group(*filas), title=f"[bold]📝 Plan: desinstalar {prog.nombre}[/]", title_align="left",
                 border_style="cyan", box=box.ROUNDED, padding=(0, 1))


def panel_verificacion(v: Verificacion, nombre: str) -> Panel:
    filas: list = []
    if v.limpio:
        filas.append(Text("✔ Rastro: 0", style="bold green"))
    for q in v.quedan:
        filas.append(Text(f"✘ quedó: {q}", style="yellow"))
    for h in v.nuevos:
        for i in h.detalle:
            filas.append(Text(f"• apareció después: {i.nombre} ({humano(i.peso)})", style="yellow"))
    if v.conservados:
        filas.append(Text(f"• {len(v.conservados)} cosas que elegiste conservar siguen ahí "
                          f"({humano(sum(i.peso or 0 for i in v.conservados))}).", style="dim"))
    filas.append(Text.assemble(("Espacio liberado: ", "bold"), (humano(v.liberado), "bold green")))
    return Panel(Group(*filas), title=f"[bold]🔎 Verificación: {nombre}[/]", title_align="left",
                 border_style="green" if v.limpio else "yellow", box=box.ROUNDED, padding=(0, 1))
