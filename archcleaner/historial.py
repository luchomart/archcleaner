"""Historial: una "foto" del disco por análisis, y qué creció o se achicó entre dos fotos.

Cada foto guarda el peso de las carpetas de más de 1 MB, el espacio libre de cada disco y el
total de basura (🟢) y de cosas para revisar (🟡). Pesa unos 20-100 KB (json comprimido).

Para que no crezca para siempre se guardan: todas las de la última semana, una por semana
hasta los 3 meses y una por mes de ahí para atrás.
"""

from __future__ import annotations

import functools
import gzip
import json
import os
import shutil
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from . import estado
from .escaner import Nodo
from .modelo import Nivel
from .util import humano

UMBRAL = 1024**2          # carpetas más chicas no se guardan
MINIMO_CAMBIO = 50 * 1024**2  # en la comparación, cambios más chicos no se muestran
DIA = 86400
FORMATO = "%Y-%m-%d_%H-%M-%S"


@dataclass
class Foto:
    fecha: float
    raices: list[str] = field(default_factory=list)
    carpetas: dict[str, int] = field(default_factory=dict)
    discos: dict[str, list[int]] = field(default_factory=dict)  # punto de montaje -> [total, libre]
    seguro: int = 0
    revisar: int = 0

    @property
    def cuando(self) -> str:
        return datetime.fromtimestamp(self.fecha).strftime("%d/%m %H:%M")


def carpeta() -> Path:
    return estado.ARCHIVO.parent / "historial"


# ── Guardar y leer ───────────────────────────────────────────────────────────

def foto_de(res, ahora: float | None = None) -> Foto | None:
    """La foto de un análisis. None si no se escanearon los discos (análisis rápido)."""
    if not res.ctx.escaneos:
        return None
    f = Foto(ahora or time.time())
    for esc in res.ctx.escaneos:
        f.raices.append(esc.raiz)
        f.carpetas.update({d: b for d, b in esc.total.items() if b >= UMBRAL or d == esc.raiz})
    for punto in dict.fromkeys(["/"] + [r for r in f.raices if os.path.ismount(r)]):
        try:
            u = shutil.disk_usage(punto)
            f.discos[punto] = [u.total, u.free]
        except OSError:
            pass
    f.seguro = sum(h.peso or 0 for h in res.hallazgos if h.nivel == Nivel.SEGURO and h.suma)
    f.revisar = sum(h.peso or 0 for h in res.hallazgos if h.nivel == Nivel.REVISAR and h.suma)
    return f


def guardar(foto: Foto) -> Path | None:
    d = carpeta()
    ruta = d / (datetime.fromtimestamp(foto.fecha).strftime(FORMATO) + ".json.gz")
    try:
        d.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(gzip.compress(json.dumps(foto.__dict__, ensure_ascii=False).encode()))
    except OSError:
        return None
    podar(foto.fecha)
    return ruta


def listar() -> list[tuple[float, Path]]:
    """(fecha, archivo) de cada foto, de la más vieja a la más nueva."""
    res = []
    try:
        archivos = list(carpeta().glob("*.json.gz"))
    except OSError:
        return res
    for a in archivos:
        try:
            res.append((datetime.strptime(a.name.removesuffix(".json.gz"), FORMATO).timestamp(), a))
        except ValueError:
            continue
    return sorted(res)


def cargar(ruta: Path) -> Foto | None:
    try:
        return _cargar(str(ruta), ruta.stat().st_mtime)
    except OSError:
        return None


@functools.lru_cache(maxsize=64)
def _cargar(ruta: str, _mtime: float) -> Foto | None:
    """Las fotos no cambian: se leen una vez (el menú se redibuja seguido y muestra varias)."""
    try:
        return Foto(**json.loads(gzip.decompress(Path(ruta).read_bytes())))
    except (OSError, ValueError, TypeError, EOFError):
        return None


def que_borrar(fechas: list[float], ahora: float) -> list[float]:
    """Cuáles fotos sobran: se queda con todas las de 7 días, una por semana hasta 90 y una por mes."""
    quedan: set[float] = set()
    vistos: set[tuple] = set()
    for f in sorted(fechas, reverse=True):  # de la más nueva a la más vieja: queda la más nueva de cada grupo
        edad = (ahora - f) / DIA
        dt = datetime.fromtimestamp(f)
        if edad < 7:
            quedan.add(f)
            continue
        grupo = ("semana", *dt.isocalendar()[:2]) if edad < 90 else ("mes", dt.year, dt.month)
        if grupo not in vistos:
            vistos.add(grupo)
            quedan.add(f)
    return [f for f in fechas if f not in quedan]


def podar(ahora: float | None = None) -> int:
    fotos = listar()
    sobran = set(que_borrar([f for f, _ in fotos], ahora or time.time()))
    borradas = 0
    for f, ruta in fotos:
        if f in sobran:
            try:
                ruta.unlink()
                borradas += 1
            except OSError:
                pass
    return borradas


def anterior(fecha: float, dias: float | None = None) -> Foto | None:
    """La foto con la que comparar una de `fecha`: la anterior, o la más nueva de hace al menos `dias`.

    Si no hay ninguna tan vieja, la más vieja que haya.
    """
    previas = [(f, r) for f, r in listar() if f < int(fecha)]  # los archivos tienen la hora al segundo: la propia foto queda afuera
    if not previas:
        return None
    if dias is not None:
        tope = fecha - dias * DIA
        candidatas = [(f, r) for f, r in previas if f <= tope]
        elegida = candidatas[-1] if candidatas else previas[0]
    else:
        elegida = previas[-1]
    return cargar(elegida[1])


def ultima() -> Foto | None:
    fotos = listar()
    return cargar(fotos[-1][1]) if fotos else None


def libre_en_el_tiempo(punto: str = "/", cuantas: int = 14) -> list[int]:
    """Espacio libre de un disco en las últimas fotos (para la mini gráfica del menú)."""
    res = []
    for _, ruta in listar()[-cuantas:]:
        f = cargar(ruta)
        if f and punto in f.discos:
            res.append(f.discos[punto][1])
    return res


def chispa(valores: list[int]) -> str:
    """Mini gráfica de barras: ▁▂▃▄▅▆▇█."""
    if not valores:
        return ""
    bajo, alto = min(valores), max(valores)
    niveles = "▁▂▃▄▅▆▇█"
    if alto == bajo:
        return "▄" * len(valores)
    return "".join(niveles[round((v - bajo) / (alto - bajo) * 7)] for v in valores)


# ── Comparar ─────────────────────────────────────────────────────────────────

@dataclass
class Comparacion:
    antes: Foto
    despues: Foto
    crecio: list[Nodo]          # un árbol por raíz (solo lo que creció)
    achico: list[Nodo]          # un árbol por raíz (solo lo que se achicó; pesos positivos)
    nuevas: set[str]            # carpetas que no estaban en la foto vieja
    borradas: set[str]          # carpetas que ya no están

    @property
    def dias(self) -> float:
        return (self.despues.fecha - self.antes.fecha) / DIA


def comparar(antes: Foto, despues: Foto, minimo: int = MINIMO_CAMBIO) -> Comparacion:
    viejas, nuevas_c = antes.carpetas, despues.carpetas
    delta = {d: nuevas_c.get(d, 0) - viejas.get(d, 0) for d in set(viejas) | set(nuevas_c)}
    raices = [r for r in despues.raices if r in antes.raices]
    # "nueva" = no estaba pero su carpeta madre sí (si la madre tampoco estaba, la nueva es la madre)
    nuevas = {d for d in nuevas_c if d not in viejas and os.path.dirname(d) in viejas and d not in raices}
    borradas = {d for d in viejas if d not in nuevas_c and os.path.dirname(d) in nuevas_c and d not in raices}

    hijos: dict[str, list[str]] = defaultdict(list)
    for d in delta:
        if d != os.path.dirname(d):  # "/" no es hija de sí misma
            hijos[os.path.dirname(d)].append(d)

    def arbol(raiz: str, signo: int) -> Nodo:
        def cambio(d: str) -> int:
            return delta[d] * signo

        def grandes(d: str) -> list[str]:
            if d in nuevas or d in borradas:  # adentro de una carpeta nueva/borrada no hace falta bajar
                return []
            return sorted((h for h in hijos[d] if cambio(h) >= minimo and not _excluida(h, despues, raiz)),
                          key=cambio, reverse=True)

        def construir(d: str, base: str, prof: int) -> Nodo:
            kids = grandes(d)
            while len(kids) == 1 and cambio(kids[0]) >= 0.9 * cambio(d):
                d = kids[0]
                kids = grandes(d)
            nodo = Nodo(ruta=d, etiqueta=os.path.relpath(d, base) if base else d, peso=cambio(d))
            if prof < 5:
                nodo.hijos = [construir(k, d, prof + 1) for k in kids[:6]]
            nodo.resto = nodo.peso - sum(h.peso for h in nodo.hijos)
            return nodo

        nodo = Nodo(ruta=raiz, etiqueta=raiz, peso=cambio(raiz))
        nodo.hijos = [construir(k, raiz, 1) for k in grandes(raiz)[:8]]
        return nodo

    return Comparacion(antes, despues, [arbol(r, 1) for r in raices], [arbol(r, -1) for r in raices],
                       nuevas, borradas)


def _excluida(d: str, foto: Foto, raiz: str) -> bool:
    """Una carpeta que es la raíz de otro escaneo (ej. el home adentro de /) no se cuenta dos veces."""
    return d in foto.raices and d != raiz


def culpables(comp: Comparacion, cuantos: int = 3) -> list[tuple[str, int]]:
    """Las carpetas que más explican el crecimiento: las hojas del árbol (o lo que sus hijas no explican)."""
    res: list[tuple[str, int]] = []

    def recorrer(n: Nodo) -> None:
        if not n.hijos:
            res.append((n.ruta, n.peso))
            return
        if n.resto >= MINIMO_CAMBIO:
            res.append((n.ruta, n.resto))
        for h in n.hijos:
            recorrer(h)

    for raiz in comp.crecio:
        for h in raiz.hijos:
            recorrer(h)
    return sorted(res, key=lambda x: x[1], reverse=True)[:cuantos]


# ── Paneles ──────────────────────────────────────────────────────────────────

def _corto(ruta: str, home: str) -> str:
    return "~" + ruta[len(home):] if ruta == home or ruta.startswith(home + "/") else ruta


def _signo(b: int) -> str:
    return ("+" if b > 0 else "−" if b < 0 else "±") + humano(abs(b))


def hace_dias(dias: float) -> str:
    if dias < 1:
        horas = round(dias * 24)
        return "hace menos de una hora" if horas < 1 else f"hace {horas} h"
    return "hace 1 día" if round(dias) == 1 else f"hace {round(dias)} días"


def panel_resumen(comp: Comparacion) -> Panel:
    """Tarjeta corta para arriba del informe: espacio libre y lo que más creció."""
    home = str(Path.home())
    filas = Table.grid(padding=(0, 2))
    filas.add_column(style="bold")
    filas.add_column(justify="right")
    filas.add_column()
    for punto, (_, libre) in comp.despues.discos.items():
        if punto in comp.antes.discos:
            d = libre - comp.antes.discos[punto][1]
            filas.add_row(punto, Text(_signo(d), style="red" if d < 0 else "green"),
                          Text("de espacio libre", style="dim"))
    cuerpo: list = [filas]
    top = culpables(comp)
    if top:
        cuerpo.append(Text("\nLo que más creció:", style="bold"))
        for ruta, b in top:
            cuerpo.append(Text.assemble((f"  {_signo(b):>10}  ", "bold yellow"), _corto(ruta, home)))
    else:
        cuerpo.append(Text(f"\nNinguna carpeta creció más de {humano(MINIMO_CAMBIO)}.", style="dim"))
    titulo = f"[bold]📈 Desde el análisis del {comp.antes.cuando}[/] [dim]({hace_dias(comp.dias)})[/]"
    return Panel(Group(*cuerpo), title=titulo, title_align="left", border_style="magenta", box=box.ROUNDED)


def paneles(comp: Comparacion) -> list:
    """La comparación completa (pantalla «Qué creció» y `archcleaner crecio`)."""
    home = str(Path.home())
    res: list = [Text.assemble(
        ("Comparando el análisis del ", "dim"), (comp.despues.cuando, "bold"), (" con el del ", "dim"),
        (comp.antes.cuando, "bold"), (f"  ({hace_dias(comp.dias)} antes)", "dim"))]

    # discos y basura
    t = Table(box=box.SIMPLE_HEAD, expand=False, padding=(0, 2))
    t.add_column("")
    t.add_column("Antes", justify="right")
    t.add_column("Ahora", justify="right")
    t.add_column("Cambio", justify="right")
    for punto, (_, libre) in comp.despues.discos.items():
        if punto in comp.antes.discos:
            antes = comp.antes.discos[punto][1]
            t.add_row(f"💽 Libre en {punto}", humano(antes), humano(libre),
                      Text(_signo(libre - antes), style="red" if libre < antes else "green"))
    for nombre, a, b in (("🟢 Basura sin riesgo", comp.antes.seguro, comp.despues.seguro),
                         ("🟡 Para revisar", comp.antes.revisar, comp.despues.revisar)):
        t.add_row(nombre, humano(a), humano(b), Text(_signo(b - a), style="yellow" if b > a else "green"))
    res.append(Panel(t, title="[bold]Resumen[/]", title_align="left", border_style="grey50", box=box.ROUNDED))

    for arboles, titulo, color, vacio in (
            (comp.crecio, "📈 Lo que creció", "yellow", "Nada creció más de {}."),
            (comp.achico, "📉 Lo que se achicó", "green", "Nada se achicó más de {}.")):
        partes: list = []
        for raiz in arboles:
            if not raiz.hijos:
                continue
            nombre = "~ (tu home)" if raiz.ruta == home else "/ (sistema, sin tu home)" if raiz.ruta == "/" \
                else raiz.ruta
            neto = raiz.peso if color == "yellow" else -raiz.peso
            arbol = Tree(Text.assemble((nombre, "bold cyan"), (f"   (cambio neto: {_signo(neto)})", "dim")),
                         guide_style="grey35")
            _ramas(arbol, raiz, color, comp)
            partes.append(arbol)
        if not partes:
            partes = [Text(vacio.format(humano(MINIMO_CAMBIO)), style="dim")]
        res.append(Panel(Group(*partes), title=f"[bold]{titulo}[/]", title_align="left", border_style=color,
                         box=box.ROUNDED, padding=(0, 1)))
    res.append(Text(f"Solo se muestran cambios de más de {humano(MINIMO_CAMBIO)}. «nueva» = no estaba en el "
                    "análisis anterior; «ya no está» = se borró.", style="dim"))
    return res


def _ramas(t: Tree, nodo: Nodo, color: str, comp: Comparacion) -> None:
    signo = "+" if color == "yellow" else "−"
    for h in nodo.hijos:
        linea = Text.assemble((f"{signo + humano(h.peso):>10} ", f"bold {color}"), " ", h.etiqueta)
        if h.ruta in comp.nuevas:
            linea.append("  nueva", style="magenta")
        elif h.ruta in comp.borradas:
            linea.append("  ya no está", style="magenta")
        _ramas(t.add(linea), h, color, comp)


def sin_historial(fotos: int, en_app: bool = True) -> Text:
    analizar = "tocá 🔄 Actualizar" if en_app else "corré «archcleaner analizar»"
    if fotos == 0:
        return Text("Todavía no hay historial: se empieza a guardar con cada análisis completo. "
                    f"Analizá hoy ({analizar}) y volvé otro día para ver qué creció.")
    return Text("Hay un solo análisis guardado: hace falta otro para comparar. "
                f"Volvé a analizar más adelante (o {analizar} para analizar ahora).")
