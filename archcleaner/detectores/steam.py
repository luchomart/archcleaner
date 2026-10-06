"""Steam: restos de juegos desinstalados, descargas a medias, Proton sin usar y peso de cada juego."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from rich.cells import cell_len, set_cell_size

from ..contexto import Contexto
from ..modelo import Hallazgo, Item, Limpieza, Modo, Nivel, items_ordenados
from ..util import leer_vdf
from ..i18n import tr

MINIMO = 1024**2
WORKSHOP_GRANDE = 2 * 1024**3
ID_NO_STEAM = 2**31  # los accesos directos "juego no-Steam" usan IDs altísimos
STEAM = ["steam"]   # proceso que tiene que estar cerrado para tocar sus carpetas

CARPETAS_PARTIDAS = (
    "Documents", "My Documents", "Saved Games",
    "AppData/Roaming", "AppData/Local", "AppData/LocalLow",
)


def _raiz_steam(home: Path) -> Path | None:
    for c in (home / ".local/share/Steam", home / ".steam/steam"):
        if (c / "steamapps").is_dir():
            return Path(os.path.realpath(c))
    return None


def _bibliotecas(raiz: Path) -> list[Path]:
    libs = [raiz]
    for archivo in (raiz / "steamapps/libraryfolders.vdf", raiz / "config/libraryfolders.vdf"):
        datos = leer_vdf(archivo).get("libraryfolders", {})
        for v in datos.values():
            ruta = v.get("path") if isinstance(v, dict) else None
            if ruta and (Path(ruta) / "steamapps").is_dir():
                p = Path(os.path.realpath(ruta))
                if p not in libs:
                    libs.append(p)
    return libs


def _manifiestos(lib: Path) -> dict[str, dict]:
    """appid -> datos del appmanifest (name, installdir, sizeondisk)."""
    res = {}
    for f in (lib / "steamapps").glob("appmanifest_*.acf"):
        datos = leer_vdf(f).get("appstate", {})
        if datos.get("appid"):
            res[datos["appid"]] = datos
    return res


def _subcarpetas(d: Path) -> list[Path]:
    try:
        return sorted(p for p in d.iterdir() if p.is_dir())
    except OSError:
        return []


def detectar(ctx: Contexto) -> list[Hallazgo]:
    raiz = _raiz_steam(ctx.home)
    if not raiz:
        return []
    libs = _bibliotecas(raiz)
    ctx.steam_bibliotecas = libs

    por_lib = {lib: _manifiestos(lib) for lib in libs}
    instalados = {appid for m in por_lib.values() for appid in m}
    nombres = {appid: d.get("name", appid) for m in por_lib.values() for appid, d in m.items()}

    res: list[Hallazgo] = []
    for lib in libs:
        sa = lib / "steamapps"
        manifiestos = por_lib[lib]
        _etiquetar(ctx, sa, manifiestos)
        res += _juegos(lib, manifiestos)
        res += _huerfanos_common(ctx, lib, manifiestos)
        res += _por_appid(ctx, lib, sa / "shadercache", instalados, Nivel.SEGURO,
                          tr("Shader cache de juegos desinstalados"),
                          tr("Shaders precompilados de juegos que ya no tenés. Si reinstalás el juego, se regeneran."))
        res += _por_appid(ctx, lib, sa / "workshop/content", instalados, Nivel.SEGURO,
                          tr("Contenido de Workshop de juegos desinstalados"),
                          tr("Mods/contenido de Workshop de juegos que ya no están instalados."))
        res += _compatdata(ctx, lib, sa / "compatdata", instalados)
        res += _workshop_grande(ctx, lib, sa / "workshop/content", instalados, nombres)
        for sub, titulo in (("downloading", tr("Descargas a medias")), ("temp", tr("Temporales de Steam")),
                            ("workshop/downloads", tr("Descargas a medias de Workshop")),
                            ("workshop/temp", tr("Temporales de Workshop"))):
            res += _carpeta_temporal(ctx, lib, sa / sub, titulo)
    res += _proton_sin_uso(ctx, raiz)
    return res


def _etiquetar(ctx: Contexto, sa: Path, manifiestos: dict[str, dict]) -> None:
    for appid, d in manifiestos.items():
        nombre = d.get("name", appid)
        ctx.nombres_conocidos.update({nombre, d.get("installdir", "")})
        if d.get("installdir"):
            ctx.etiquetas[str(sa / "common" / d["installdir"])] = tr("juego: {nombre}", nombre=nombre)
        for sub, que in (("workshop/content", "workshop"), ("compatdata", "Proton"), ("shadercache", "shaders")):
            ctx.etiquetas[str(sa / sub / appid)] = tr("{que} de {nombre}", que=que, nombre=nombre)


def _juegos(lib: Path, manifiestos: dict[str, dict]) -> list[Hallazgo]:
    if not manifiestos:
        return []
    detalle = items_ordenados([Item(d.get("name", appid), int(d.get("sizeondisk") or 0))
                               for appid, d in manifiestos.items()])
    return [Hallazgo(
        tr("Steam"), tr("Juegos instalados en {lib}", lib=lib), Nivel.INFO, sum(i.peso or 0 for i in detalle),
        tr("Lo que pesa cada juego (y herramientas como Proton). Si alguno no lo jugás más, "
          "desinstalalo desde Steam."),
        rutas=[lib / "steamapps/common"], detalle=detalle, suma=False,
    )]


def _huerfanos_common(ctx: Contexto, lib: Path, manifiestos: dict[str, dict]) -> list[Hallazgo]:
    common = lib / "steamapps/common"
    usadas = {d.get("installdir", "").lower() for d in manifiestos.values()}
    detalle, rutas, inc_total = [], [], False
    for d in _subcarpetas(common):
        if d.name.lower() in usadas:
            continue
        peso, inc = ctx.medir(d)
        inc_total |= inc
        if peso and peso >= MINIMO:
            detalle.append(Item(d.name, peso, d))
            rutas.append(d)
            ctx.reclamar(d)
            ctx.etiquetas[str(d)] = tr("resto de juego desinstalado")
    if not detalle:
        return []
    return [Hallazgo(
        tr("Steam"), tr("Carpetas de juegos que Steam ya no reconoce ({lib})", lib=lib), Nivel.REVISAR,
        sum(i.peso or 0 for i in detalle),
        tr("Están en steamapps/common pero ningún juego instalado las usa: suelen quedar al "
          "desinstalar (mods, configs, archivos que agregaste vos). Puede haber partidas guardadas."),
        rutas=rutas, detalle=items_ordenados(detalle), incompleto=inc_total,
        limpieza=Limpieza(Modo.PAPELERA, por_item=True, cerrar=STEAM),
    )]


def _por_appid(ctx: Contexto, lib: Path, base: Path, instalados: set[str], nivel: Nivel,
               titulo: str, explicacion: str) -> list[Hallazgo]:
    detalle, rutas = [], []
    for d in _subcarpetas(base):
        if not d.name.isdigit() or d.name in instalados:
            continue
        if int(d.name) >= ID_NO_STEAM:
            ctx.etiquetas[str(d)] = tr("de un juego no-Steam (acceso directo)")
            continue
        peso, _ = ctx.medir(d)
        if peso and peso >= MINIMO:
            detalle.append(Item(f"appid {d.name}", peso, d))
            rutas.append(d)
            ctx.reclamar(d)
    if not detalle:
        return []
    return [Hallazgo(
        tr("Steam"), f"{titulo} ({lib})", nivel, sum(i.peso or 0 for i in detalle), explicacion,
        rutas=rutas, detalle=items_ordenados(detalle),
        limpieza=Limpieza(Modo.BORRAR, por_item=True, cerrar=STEAM),
    )]


def _tiene_partidas(prefijo: Path) -> bool:
    usuario = prefijo / "pfx/drive_c/users/steamuser"
    for sub in CARPETAS_PARTIDAS:
        for _, _, archivos in os.walk(usuario / sub):
            if archivos:
                return True
    return False


def _compatdata(ctx: Contexto, lib: Path, base: Path, instalados: set[str]) -> list[Hallazgo]:
    detalle, rutas = [], []
    for d in _subcarpetas(base):
        if not d.name.isdigit() or d.name in instalados or d.name == "0":
            continue
        if int(d.name) >= ID_NO_STEAM:
            ctx.etiquetas[str(d)] = tr("de un juego no-Steam (acceso directo)")
            continue
        peso, _ = ctx.medir(d)
        if not peso or peso < MINIMO:
            continue
        marca = tr("  ⚠ puede tener partidas guardadas") if _tiene_partidas(d) else ""
        detalle.append(Item(f"appid {d.name}{marca}", peso, d))
        rutas.append(d)
        ctx.reclamar(d)
    if not detalle:
        return []
    return [Hallazgo(
        tr("Steam"), tr("Prefijos de Proton de juegos desinstalados ({lib})", lib=lib), Nivel.REVISAR,
        sum(i.peso or 0 for i in detalle),
        tr("Cada juego de Windows tiene su propio 'Windows falso' (compatdata). Steam no lo borra al "
          "desinstalar porque ahí adentro suelen estar las PARTIDAS GUARDADAS. Si no vas a volver a "
          "jugar (o el juego guarda en la nube), se puede borrar."),
        rutas=rutas, detalle=items_ordenados(detalle),
        limpieza=Limpieza(Modo.PAPELERA, por_item=True, cerrar=STEAM),
    )]


def _workshop_grande(ctx: Contexto, lib: Path, base: Path, instalados: set[str],
                     nombres: dict[str, str]) -> list[Hallazgo]:
    res = []
    for d in _subcarpetas(base):
        if d.name not in instalados:
            continue
        peso, _ = ctx.medir(d)
        if not peso or peso < WORKSHOP_GRANDE:
            continue
        items = []
        for s in _subcarpetas(d):
            nombre = nombre_workshop(s)
            if nombre:
                ctx.etiquetas[str(s)] = tr("workshop: {nombre}", nombre=nombre)
            items.append(Item(f"{_recortar(nombre, 50)}  ({s.name})" if nombre else s.name, ctx.medir(s)[0]))
        items = items_ordenados(items)
        res.append(Hallazgo(
            tr("Steam"), tr("Workshop de {juego}", juego=nombres.get(d.name, d.name)), Nivel.REVISAR, peso,
            tr("Contenido de Workshop al que estás suscripto ({n} ítems). Si lo borrás a mano, "
              "Steam lo vuelve a bajar: la forma correcta es desuscribirte en Steam de lo que no uses. "
              "Entre paréntesis va el ID: steamcommunity.com/sharedfiles/filedetails/?id=ID te lleva a su página.",
              n=len(items)),
            rutas=[d], detalle=items, suma=False,
        ))
    return res


_ARCHIVOS_NOMBRE = ("project.json", "pack.json", "modinfo.json", "mod.json", "info.json", "metadata.json")
_CLAVES_NOMBRE = ("title", "Title", "name", "Name", "displayName", "DisplayName")
_COLOR_TERRARIA = re.compile(r"\[c/[0-9A-Fa-f]{6}:([^\]]*)\]")


def nombre_workshop(d: Path) -> str | None:
    """El nombre de un ítem de Workshop, si el propio ítem lo trae (cada juego lo guarda distinto)."""
    for archivo in _ARCHIVOS_NOMBRE:
        try:
            datos = json.loads((d / archivo).read_text(encoding="utf-8-sig", errors="replace")[:200_000])
        except (OSError, ValueError):
            continue
        if isinstance(datos, dict):
            for clave in _CLAVES_NOMBRE:
                if isinstance(datos.get(clave), str) and datos[clave].strip():
                    return _limpiar_nombre(datos[clave])
    for archivo, patron in (("About/About.xml", r"<name>([^<]+)</name>"),  # RimWorld
                            ("descriptor.mod", r'^name\s*=\s*"([^"]+)"')):  # juegos de Paradox
        try:
            m = re.search(patron, (d / archivo).read_text(errors="replace")[:200_000], re.M)
        except OSError:
            continue
        if m and m.group(1).strip():
            return _limpiar_nombre(m.group(1))
    return None


def _recortar(texto: str, ancho: int) -> str:
    """Corta al final según el ancho en pantalla (un carácter chino ocupa dos columnas)."""
    return texto if cell_len(texto) <= ancho else set_cell_size(texto, ancho - 1).rstrip() + "…"


def _limpiar_nombre(texto: str) -> str:
    texto = _COLOR_TERRARIA.sub(r"\1", texto)
    return " ".join(texto.split())


def _carpeta_temporal(ctx: Contexto, lib: Path, d: Path, titulo: str) -> list[Hallazgo]:
    if not d.is_dir():
        return []
    peso, _ = ctx.medir(d)
    if not peso or peso < MINIMO:
        return []
    ctx.reclamar(d)
    return [Hallazgo(
        tr("Steam"), f"{titulo} ({lib})", Nivel.SEGURO, peso,
        tr("Archivos temporales de Steam. Si tenés una descarga pausada que querés retomar, "
          "esperá a que termine; si no, se pueden borrar (con Steam cerrado)."),
        rutas=[d], limpieza=Limpieza(Modo.VACIAR, cerrar=STEAM),
    )]


def _proton_sin_uso(ctx: Contexto, raiz: Path) -> list[Hallazgo]:
    """Versiones de Proton instaladas a mano (compatibilitytools.d) que ningún juego tiene asignadas."""
    config = leer_vdf(raiz / "config/config.vdf")
    mapeo = (config.get("installconfigstore", {}).get("software", {}).get("valve", {})
             .get("steam", {}).get("compattoolmapping", {}))
    usados = {v.get("name", "").lower() for v in mapeo.values() if isinstance(v, dict)}

    detalle, rutas = [], []
    for d in _subcarpetas(raiz / "compatibilitytools.d"):
        vdf = leer_vdf(d / "compatibilitytool.vdf")
        internos = set(vdf.get("compatibilitytools", {}).get("compat_tools", {}).keys()) or {d.name.lower()}
        if internos & usados:
            continue
        peso, _ = ctx.medir(d)
        if peso and peso >= MINIMO:
            detalle.append(Item(d.name, peso, d))
            rutas.append(d)
            ctx.etiquetas[str(d)] = tr("Proton que ningún juego de Steam usa")
    if not detalle:
        return []
    return [Hallazgo(
        tr("Steam"), tr("Versiones de Proton que ningún juego de Steam usa"), Nivel.REVISAR,
        sum(i.peso or 0 for i in detalle),
        tr("Están en compatibilitytools.d pero no hay ningún juego de Steam configurado para usarlas. "
          "OJO: launchers como Heroic, Lutris o umu pueden estar usándolas por fuera de Steam."),
        rutas=rutas, detalle=items_ordenados(detalle),
        limpieza=Limpieza(Modo.PAPELERA, por_item=True, cerrar=STEAM),
    )]
