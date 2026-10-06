"""Archivos gigantes encontrados en los escaneos (fuera de lo que ya explicó otro detector).

Las carpetas que parecen instaladores (tienen un setup.exe al lado de los archivos grandes)
se reportan aparte: si el programa ya está instalado, el instalador suele sobrar. Y los archivos
que son parte de un juego instalado por fuera de Steam (Hydra, repacks, GOG...) se agrupan por
juego, con el peso de toda su carpeta: no son basura sueltas, son el juego.
"""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

from ..contexto import Contexto
from ..modelo import Hallazgo, Item, Limpieza, Modo, Nivel, items_ordenados
from ..util import dentro_de

LIMITE = 25
NOMBRES_INSTALADOR = {"setup.exe", "install.exe", "installer.exe"}
SUBIR_MAX = 6  # cuántas carpetas se sube desde un archivo gigante buscando la raíz del juego


def detectar(ctx: Contexto) -> list[Hallazgo]:
    excluir = list(ctx.reclamadas) + [str(lib / "steamapps") for lib in ctx.steam_bibliotecas]
    excluir.append("/usr")
    archivos = []
    for esc in ctx.escaneos:
        for peso, ruta in esc.grandes:
            if not any(dentro_de(ruta, e) for e in excluir):
                archivos.append((peso, ruta))
    if not archivos:
        return []

    instaladores = _carpetas_instalador(archivos)
    res = []
    if instaladores:
        detalle, rutas = [], []
        for d in instaladores:
            peso, _ = ctx.medir(d)
            detalle.append(Item(_corto(ctx, d), peso, Path(d)))
            rutas.append(Path(d))
            ctx.reclamar(d)
        res.append(Hallazgo(
            "Archivos", "Instaladores de juegos/programas", Nivel.REVISAR, sum(i.peso or 0 for i in detalle),
            "Carpetas con un instalador (setup.exe) y archivos enormes al lado. Si el juego o programa "
            "ya está instalado y funciona, el instalador sobra (salvo que lo quieras para reinstalar).",
            rutas=rutas, detalle=items_ordenados(detalle),
            limpieza=Limpieza(Modo.PAPELERA, por_item=True),
        ))

    restantes = [a for a in archivos if not any(dentro_de(a[1], d) for d in instaladores)]
    juegos = _carpetas_juego(restantes, _limites(ctx))
    if juegos:
        detalle = []
        for d in juegos:
            peso, _ = ctx.medir(d)
            detalle.append(Item(f"{os.path.basename(d)}  ({_corto(ctx, os.path.dirname(d))})", peso, Path(d)))
            ctx.reclamar(d)
        res.append(Hallazgo(
            "Archivos", "Juegos instalados por fuera de Steam", Nivel.REVISAR, sum(i.peso or 0 for i in detalle),
            "No es basura: son juegos instalados a mano (Hydra, repacks, GOG...). Se muestran porque "
            "pesan mucho: si ya no jugás alguno, borrar su carpeta libera todo eso. Ojo: con Proton/Wine "
            "las partidas suelen guardarse en el prefijo, no acá, así que borrar el juego no las borra.",
            rutas=[i.ruta for i in detalle], detalle=items_ordenados(detalle),
            limpieza=Limpieza(Modo.PAPELERA, por_item=True),
        ))

    sueltos = sorted((a for a in restantes if not any(dentro_de(a[1], d) for d in juegos)), reverse=True)
    if sueltos:
        res.append(Hallazgo(
            "Archivos", "Archivos gigantes (más de 1 GB)", Nivel.REVISAR, sum(p for p, _ in sueltos),
            "No se sabe si sobran: pueden ser juegos instalados por fuera de Steam, máquinas virtuales, "
            "videos o ISOs. Fijate si te conviene quedártelos.",
            rutas=[Path(r) for _, r in sueltos[:LIMITE]],
            detalle=[Item(_corto(ctx, r), p, Path(r)) for p, r in sueltos[:LIMITE]], suma=False,
            limpieza=Limpieza(Modo.PAPELERA, por_item=True),
        ))
    return res


def _carpetas_instalador(archivos: list[tuple[int, str]]) -> list[str]:
    por_carpeta: dict[str, int] = defaultdict(int)
    for peso, ruta in archivos:
        por_carpeta[os.path.dirname(ruta)] += peso
    res = []
    for d in por_carpeta:
        try:
            nombres = {n.lower() for n in os.listdir(d)}
        except OSError:
            continue
        if nombres & NOMBRES_INSTALADOR:
            res.append(d)
    return res


def _limites(ctx: Contexto) -> set[str]:
    """Carpetas por encima de las cuales nunca se sube (el home, los discos, la raíz)."""
    res = {"/", str(ctx.home), "/mnt", "/media", "/run/media"}
    try:
        with open("/proc/self/mounts") as f:
            res.update(linea.split()[1].replace("\\040", " ") for linea in f)
    except OSError:
        pass
    return res


def _es_raiz_juego(d: str) -> bool:
    """Una carpeta con un .exe adentro, o con la forma de un juego de Unreal o de Unity."""
    try:
        entradas = list(os.scandir(d))
    except OSError:
        return False
    nombres = {e.name.lower() for e in entradas}
    if any(n.endswith(".exe") for n in nombres) or "unityplayer.dll" in nombres:
        return True
    return "engine" in nombres and any(
        e.is_dir() and os.path.isdir(os.path.join(e.path, "Binaries")) for e in entradas if e.name != "Engine")


def _carpetas_juego(archivos: list[tuple[int, str]], limites: set[str]) -> list[str]:
    """La carpeta del juego de cada archivo: la más cercana, subiendo, que parezca la raíz de un juego."""
    res: set[str] = set()
    for _, ruta in archivos:
        d = os.path.dirname(ruta)
        for _ in range(SUBIR_MAX):
            if d in limites or d == os.path.dirname(d):
                break
            if _es_raiz_juego(d):
                res.add(d)
                break
            d = os.path.dirname(d)
    # si una quedó adentro de otra (un juego dentro de la carpeta de otro), vale la de afuera
    return sorted(d for d in res if not any(d != o and dentro_de(d, o) for o in res))


def _corto(ctx: Contexto, ruta: str) -> str:
    home = str(ctx.home)
    return "~" + ruta[len(home):] if ruta.startswith(home) else ruta
