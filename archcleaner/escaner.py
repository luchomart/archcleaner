"""Escáner de disco: mide cuánto ocupa cada carpeta (espacio real en disco, como `du`).

- No sigue enlaces simbólicos y no se mete en otros discos montados.
- Los hardlinks se cuentan una sola vez.
- Las carpetas sin permiso se anotan aparte en lugar de inventar números.
"""

from __future__ import annotations

import os
import stat
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from .util import dentro_de

GB = 1024**3


@dataclass
class ResultadoEscaneo:
    raiz: str
    total: dict[str, int] = field(default_factory=dict)        # carpeta -> bytes (incluye subcarpetas)
    grandes: list[tuple[int, str]] = field(default_factory=list)  # archivos >= umbral
    sin_permiso: list[str] = field(default_factory=list)
    excluidas: list[str] = field(default_factory=list)

    @property
    def peso(self) -> int:
        return self.total.get(self.raiz, 0)

    def contiene(self, ruta: str) -> bool:
        return dentro_de(ruta, self.raiz) and not any(dentro_de(ruta, e) for e in self.excluidas)

    def incompleto(self, ruta: str) -> bool:
        return any(dentro_de(s, ruta) for s in self.sin_permiso)

    def hijos(self, carpeta: str) -> list[tuple[str, int]]:
        prefijo = carpeta.rstrip("/") + "/"
        res = [
            (d, s) for d, s in self.total.items()
            if d.startswith(prefijo) and "/" not in d[len(prefijo):]
        ]
        return sorted(res, key=lambda x: x[1], reverse=True)


def escanear(
    raiz: str,
    excluir: tuple[str, ...] = (),
    umbral_grande: int = GB,
    progreso: Callable[[int, str, int], None] | None = None,
) -> ResultadoEscaneo:
    """`progreso(carpetas, carpeta_actual, bytes_medidos)` se llama cada tanto (varias veces por segundo)."""
    raiz = os.path.realpath(raiz)
    res = ResultadoEscaneo(raiz=raiz, excluidas=[os.path.realpath(e) for e in excluir])
    excluidas = set(res.excluidas)
    try:
        dispositivo = os.stat(raiz).st_dev
    except OSError:
        return res

    propio: dict[str, int] = {}
    vistos: set[tuple[int, int]] = set()
    pila = [raiz]
    contador = 0
    medido = 0
    proximo_aviso = time.monotonic()

    while pila:
        carpeta = pila.pop()
        bytes_aca = 0
        contador += 1
        if progreso and contador % 64 == 0 and time.monotonic() >= proximo_aviso:
            progreso(contador, carpeta, medido)
            proximo_aviso = time.monotonic() + 0.2
        try:
            with os.scandir(carpeta) as it:
                for e in it:
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if stat.S_ISDIR(st.st_mode):
                        bytes_aca += st.st_blocks * 512
                        if st.st_dev == dispositivo and e.path not in excluidas:
                            pila.append(e.path)
                        continue
                    if st.st_nlink > 1:
                        clave = (st.st_dev, st.st_ino)
                        if clave in vistos:
                            continue
                        vistos.add(clave)
                    b = st.st_blocks * 512
                    bytes_aca += b
                    if b >= umbral_grande and stat.S_ISREG(st.st_mode):
                        res.grandes.append((b, e.path))
        except PermissionError:
            res.sin_permiso.append(carpeta)
        except OSError:
            pass
        propio[carpeta] = bytes_aca
        medido += bytes_aca

    # Sumar de abajo hacia arriba: cada carpeta le pasa su total al padre.
    total = dict(propio)
    for carpeta in sorted(propio, key=lambda p: p.count("/"), reverse=True):
        if carpeta != raiz:
            padre = os.path.dirname(carpeta)
            if padre in total:
                total[padre] += total[carpeta]
    res.total = total
    res.grandes.sort(reverse=True)
    return res


@dataclass
class Nodo:
    ruta: str
    etiqueta: str          # ruta relativa al nodo padre (puede juntar varios niveles: "a/b/c")
    peso: int
    hijos: list[Nodo] = field(default_factory=list)
    resto: int = 0         # lo que pesan las subcarpetas chicas que no se muestran


def arbol(res: ResultadoEscaneo, minimo: int = GB, profundidad: int = 5, max_hijos: int = 8) -> Nodo:
    """Árbol del peso: solo carpetas >= `minimo`, ordenadas de mayor a menor.

    Si una carpeta tiene una única subcarpeta grande que se lleva casi todo (>= 90%),
    se juntan en un solo renglón ("steamapps/common") para no bajar nivel por nivel.
    """
    hijos: dict[str, list[str]] = defaultdict(list)
    for d in res.total:
        if d != res.raiz:
            hijos[os.path.dirname(d)].append(d)

    def grandes(d: str) -> list[str]:
        return sorted((h for h in hijos[d] if res.total[h] >= minimo), key=res.total.__getitem__, reverse=True)

    def construir(d: str, base: str, prof: int) -> Nodo:
        kids = grandes(d)
        while len(kids) == 1 and res.total[kids[0]] >= 0.9 * res.total[d]:
            d = kids[0]
            kids = grandes(d)
        nodo = Nodo(ruta=d, etiqueta=os.path.relpath(d, base) if base else d, peso=res.total[d])
        if prof < profundidad:
            nodo.hijos = [construir(k, d, prof + 1) for k in kids[:max_hijos]]
        nodo.resto = nodo.peso - sum(h.peso for h in nodo.hijos)
        return nodo

    return construir(res.raiz, "", 0)
