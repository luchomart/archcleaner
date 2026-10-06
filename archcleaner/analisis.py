"""Orquesta el análisis: escanea los discos y corre los detectores. Solo lectura."""

from __future__ import annotations

import os
import shutil
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field

from .contexto import Contexto
from .detectores import DETECTORES
from .escaner import escanear
from .modelo import Hallazgo, Nivel
from .i18n import tr


# avance(fracción 0..1, etapa, detalle): para dibujar una barra de progreso.
Avance = Callable[[float, str, str], None]
PARTE_DETECTORES = 0.4  # la primera vez (sin tiempos guardados), cuánto de la barra son los detectores


@dataclass
class Resultado:
    ctx: Contexto
    hallazgos: list[Hallazgo] = field(default_factory=list)
    # cuánto pesó y tardó cada raíz, y cuánto los detectores: el próximo análisis lo usa para estimar
    tiempos: dict = field(default_factory=dict)


def raices_por_defecto(ctx: Contexto) -> list[tuple[str, tuple[str, ...]]]:
    """(raíz, carpetas a excluir). El home, el sistema sin el home, y los discos montados en /mnt, /media, /run/media."""
    home = str(ctx.home)
    raices = [(home, ()), ("/", (home, "/timeshift"))]
    for base in ("/mnt", "/media", f"/run/media/{os.environ.get('USER', '')}"):
        try:
            for e in os.scandir(base):
                if e.is_dir(follow_symlinks=False) and os.path.ismount(e.path):
                    raices.append((e.path, ()))
        except OSError:
            pass
    return raices


class _Barra:
    """Reparte la barra entre las etapas según cuánto tardó cada una la vez anterior.

    Dentro del escaneo de una raíz, el avance es bytes medidos / bytes esperados (los de la vez
    anterior, o la primera vez lo usado en el disco). Nunca retrocede y no llega al 100 % hasta el final.
    """

    def __init__(self, raices: list[str], previos: dict, home: str, avance: Avance | None):
        self.avance = avance
        anteriores = previos.get("raices", {})
        segundos = {r: anteriores.get(r, {}).get("segundos") for r in raices}
        conocidos = [s for s in segundos.values() if s]
        # sin datos de una raíz: suponer que tarda como el promedio de las conocidas (o 1)
        promedio = sum(conocidos) / len(conocidos) if conocidos else 1.0
        pesos = {r: segundos[r] or promedio for r in raices}
        total_escaneo = sum(pesos.values())
        nombres = [n for n, _ in DETECTORES]
        antes = previos.get("detectores")
        if not isinstance(antes, dict) or not all(isinstance(antes.get(n), (int, float)) for n in nombres):
            # sin datos de cada detector: todos iguales, sumando PARTE_DETECTORES de la barra
            total_det = total_escaneo * PARTE_DETECTORES / (1 - PARTE_DETECTORES) if raices else 1.0
            antes = {n: total_det / len(nombres) for n in nombres}
        det = {n: max(antes[n], 0.01) for n in nombres}  # ninguno en cero: igual se ve que avanza
        total = total_escaneo + sum(det.values())
        self.parte = {r: p / total for r, p in pesos.items()}
        self.parte_detector = {n: t / total for n, t in det.items()}
        self.segundos_detector = det
        self.esperado = {r: anteriores.get(r, {}).get("bytes") for r in raices}
        self.home = home
        self.hecho = 0.0   # lo que suman las etapas ya terminadas
        self.ultimo = 0.0

    def esperado_de(self, raiz: str, ya_medido: dict[str, int]) -> int:
        if self.esperado.get(raiz):
            return self.esperado[raiz]
        try:
            usado = shutil.disk_usage(raiz).used
        except OSError:
            return 1
        if raiz == "/" and self.home in ya_medido:  # el home ya se midió aparte y "/" lo excluye
            usado -= ya_medido[self.home]
        return max(usado, 1)

    def mostrar(self, fraccion: float, etapa: str, detalle: str = "") -> None:
        self.ultimo = max(self.ultimo, min(fraccion, 0.99))
        if self.avance:
            self.avance(self.ultimo, etapa, detalle)

    def dentro(self, parte: float, sub: float, etapa: str, detalle: str = "") -> None:
        self.mostrar(self.hecho + parte * min(sub, 0.98), etapa, detalle)


def analizar(
    escanear_discos: bool = True,
    aviso: Callable[[str], None] = lambda _: None,
    avance: Avance | None = None,
    previos: dict | None = None,
) -> Resultado:
    """`previos`: los `tiempos` de un análisis anterior, para que la barra de avance sea realista."""
    ctx = Contexto()
    res = Resultado(ctx, tiempos={"raices": {}})
    raices = raices_por_defecto(ctx) if escanear_discos else []
    barra = _Barra([r for r, _ in raices], previos or {}, str(ctx.home), avance)
    medidos: dict[str, int] = {}

    for i, (raiz, excluir) in enumerate(raices, 1):
        etapa = tr("Escaneando {raiz}  ({i} de {n})", raiz=raiz, i=i, n=len(raices))
        aviso(etapa)
        esperado = barra.esperado_de(raiz, medidos)
        parte = barra.parte[raiz]

        def progreso(n: int, d: str, b: int, raiz=raiz, etapa=etapa, esperado=esperado, parte=parte) -> None:
            aviso(tr("Escaneando {raiz}  ·  {n:,} carpetas  ·  {d}", raiz=raiz, n=n, d=d))
            barra.dentro(parte, b / esperado, etapa, tr("{n:,} carpetas  ·  {d}", n=n, d=d))

        barra.dentro(parte, 0, etapa)
        inicio = time.monotonic()
        esc = escanear(raiz, excluir, progreso=progreso)
        ctx.escaneos.append(esc)
        medidos[esc.raiz] = esc.peso
        res.tiempos["raices"][raiz] = {"bytes": esc.peso, "segundos": round(time.monotonic() - inicio, 2)}
        barra.hecho += parte
        barra.mostrar(barra.hecho, etapa)

    res.tiempos["detectores"] = {}
    for nombre, modulo in DETECTORES:
        aviso(f"Buscando: {nombre}")
        detalle = tr("revisando: {nombre}", nombre=tr(nombre))
        barra.mostrar(barra.hecho, tr("Buscando qué sobra"), detalle)
        inicio = time.monotonic()
        listo = threading.Event()

        def latir(nombre=nombre, inicio=inicio, listo=listo, detalle=detalle) -> None:
            # mientras el detector trabaja, la barra avanza sola según lo que tardó la vez anterior
            while not listo.wait(0.2):
                sub = (time.monotonic() - inicio) / barra.segundos_detector[nombre]
                barra.dentro(barra.parte_detector[nombre], sub * 0.9, tr("Buscando qué sobra"), detalle)

        latido = threading.Thread(target=latir, daemon=True) if avance else None
        if latido:
            latido.start()
        try:
            res.hallazgos += modulo.detectar(ctx)
        except Exception:  # un detector roto no tiene que tirar abajo todo el análisis
            ctx.avisos.append(tr("Falló el detector «{nombre}»:", nombre=tr(nombre)) + "\n" + traceback.format_exc(limit=3))
        finally:
            listo.set()
            if latido:
                latido.join()
        res.tiempos["detectores"][nombre] = round(time.monotonic() - inicio, 2)
        barra.hecho += barra.parte_detector[nombre]

    # Orden fijo (nivel, y dentro de cada nivel de más pesado a más liviano) y un número para cada uno.
    orden = list(Nivel)
    res.hallazgos.sort(key=lambda h: (orden.index(h.nivel), -(h.peso or 0)))
    for i, h in enumerate(res.hallazgos, 1):
        h.numero = i
    return res
