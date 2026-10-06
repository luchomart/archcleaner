"""Qué programas hay instalados y de dónde vienen: repos, AUR, Flatpak, AppImage y juegos de Steam.

Solo programas que instalaste vos (en pacman: los "explícitos"), no librerías ni dependencias.

Cuándo se usó cada uno, por origen:
- pacman y AppImage: la fecha de último acceso (atime) de sus ejecutables. Linux la actualiza
  (con `relatime`, el modo normal) la primera vez que se abre después de instalar/actualizar y
  después como mucho una vez por día. Si no es posterior a la instalación: "sin uso" desde entonces.
  En discos montados con `noatime` no hay dato. Timeshift (rsync) lee los archivos nuevos al hacer
  una snapshot, y eso también cambia el atime: las lecturas en el horario de una snapshot no cuentan.
- Flatpak: lo más nuevo en ~/.var/app/<id> (Flatpak la crea al abrir la app por primera vez).
- Steam: el "LastPlayed" que guarda Steam en localconfig.vdf.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .detectores.steam import _bibliotecas, _manifiestos, _raiz_steam
from .util import dentro_de, ejecutar, leer_vdf, parsear_tamano
from .i18n import tr

ORIGENES = {
    "repo": ("repos", "cyan"),
    "aur": ("AUR", "magenta"),
    "flatpak": ("Flatpak", "blue"),
    "appimage": ("AppImage", "yellow"),
    "steam": ("Steam", "green"),
}

CARPETAS_APPIMAGE = (".local/bin", "Applications", "Aplicaciones", "AppImages", "Descargas", "Downloads")
HERRAMIENTAS_STEAM = ("Proton", "Steam Linux Runtime", "Steamworks")


@dataclass
class Programa:
    id: str             # paquete, id de Flatpak, ruta del AppImage o appid de Steam
    nombre: str
    origen: str         # clave de ORIGENES
    peso: int | None
    descripcion: str = ""
    version: str = ""
    extra: dict = field(default_factory=dict)
    ultimo_uso: float | None = None   # cuándo se usó por última vez (si se sabe)
    instalado: float | None = None    # cuándo se instaló o actualizó por última vez
    uso_conocido: bool = False        # True = se puede saber si se usó (ultimo_uso None = no se usó)

    @property
    def etiqueta_origen(self) -> tuple[str, str]:
        return ORIGENES[self.origen]

    @property
    def visto_en_uso(self) -> float | None:
        """La última vez que se lo vio en uso, como mucho: si no se usó desde que se instaló, esa fecha."""
        if not self.uso_conocido:
            return None
        return self.ultimo_uso or self.instalado or 0.0


# (clave, texto del botón, función de orden)
ORDENES = {
    "tamano": (tr("Tamaño"), lambda p: -(p.peso or 0)),
    "uso": (tr("Menos usados"), lambda p: (p.visto_en_uso is None, p.visto_en_uso or 0, -(p.peso or 0))),
    "nombre": (tr("Nombre"), lambda p: p.nombre.lower()),
    "reciente": (tr("Recién instalados"), lambda p: -(p.instalado or 0)),
}


def ordenar(programas: list[Programa], orden: str) -> list[Programa]:
    return sorted(programas, key=ORDENES.get(orden, ORDENES["tamano"])[1])


def listar(home: Path | None = None) -> list[Programa]:
    home = home or Path.home()
    ignorar = _horarios_snapshots()
    res = _pacman(ignorar) + _flatpak() + _appimages(home, ignorar) + _steam(home)
    return ordenar(res, "tamano")


Horarios = list[tuple[float, float]]


def _horarios_snapshots() -> Horarios:
    """(inicio, fin) de cada snapshot de Timeshift: mientras se hace, rsync lee archivos (y les cambia el atime)."""
    from . import timeshift
    res = []
    for snap in timeshift.listar():
        inicio = snap.fecha.timestamp()
        try:
            fin = max(inicio, (snap.ruta / "info.json").stat().st_mtime)  # se escribe al terminar
        except OSError:
            fin = inicio + 1800
        res.append((inicio - 5, fin + 60))
    return res


# ── Último uso ───────────────────────────────────────────────────────────────

def _sin_atime(ruta: str) -> bool:
    """¿El disco de esa ruta está montado con noatime (no anota cuándo se lee un archivo)?"""
    mejor, opciones = "", ""
    try:
        with open("/proc/self/mounts") as f:
            for linea in f:
                partes = linea.split()
                punto = partes[1].replace("\\040", " ")
                if dentro_de(ruta, punto) and len(punto) >= len(mejor):
                    mejor, opciones = punto, partes[3]
    except OSError:
        return False
    return "noatime" in opciones.split(",")


def _uso_por_atime(prog: Programa, archivos: list[str], ignorar: Horarios) -> None:
    """Último acceso a sus ejecutables; si no es posterior a la instalación, no se usó desde entonces."""
    accesos = []
    for a in archivos:
        try:
            accesos.append(os.stat(a).st_atime)
        except OSError:
            pass
    if not accesos or _sin_atime(archivos[0]):
        return
    prog.uso_conocido = True
    usos = [t for t in accesos if not any(i <= t <= f for i, f in ignorar)]  # sin las lecturas de Timeshift
    ultimo = max(usos, default=0)
    if ultimo and (prog.instalado is None or ultimo > prog.instalado + 120):  # 2 min: lo que tarda instalar
        prog.ultimo_uso = ultimo


def _fecha_pacman(texto: str) -> float | None:
    try:
        return datetime.strptime(texto.strip(), "%a %b %d %H:%M:%S %Y").timestamp()
    except ValueError:
        return None


def _pacman(ignorar: Horarios) -> list[Programa]:
    aur = set((ejecutar(["pacman", "-Qqm"]) or "").split())
    res, actual = [], {}
    for linea in ((ejecutar(["pacman", "-Qei"]) or "") + "\n").splitlines():
        if not linea.strip():
            if actual.get("Name"):
                n = actual["Name"]
                res.append(Programa(n, n, "aur" if n in aur else "repo",
                                    parsear_tamano(actual.get("Installed Size", "")),
                                    actual.get("Description", "").replace("None", ""), actual.get("Version", ""),
                                    instalado=_fecha_pacman(actual.get("Install Date", ""))))
            actual = {}
        elif " : " in linea and not linea.startswith(" "):
            clave, valor = linea.split(" : ", 1)
            actual[clave.strip()] = valor.strip()

    # sus ejecutables (en /usr/bin, o en /opt para los que se instalan ahí)
    ejecutables: dict[str, list[str]] = {}
    if res:
        for linea in (ejecutar(["pacman", "-Ql", *(p.id for p in res)]) or "").splitlines():
            paquete, _, ruta = linea.partition(" ")
            if ruta.endswith("/"):
                continue
            if ruta.startswith("/usr/bin/") or (ruta.startswith("/opt/") and os.access(ruta, os.X_OK)):
                ejecutables.setdefault(paquete, []).append(ruta)
    for p in res:
        _uso_por_atime(p, ejecutables.get(p.id, [])[:200], ignorar)
    return res


def _flatpak() -> list[Programa]:
    sal = ejecutar(["flatpak", "list", "--app", "--columns=application,name,version,size,installation"]) or ""
    res = []
    for linea in sal.splitlines():
        partes = linea.split("\t")
        if len(partes) >= 5:
            app, nombre, version, tam, inst = partes[:5]
            prog = Programa(app, nombre or app, "flatpak", parsear_tamano(tam), app, version, {"instalacion": inst})
            _uso_flatpak(prog)
            res.append(prog)
    return res


def _uso_flatpak(prog: Programa) -> None:
    base = "/var/lib/flatpak" if prog.extra.get("instalacion") == "system" else \
        str(Path.home() / ".local/share/flatpak")
    try:
        prog.instalado = os.lstat(f"{base}/app/{prog.id}/current").st_mtime
    except OSError:
        pass
    datos = Path.home() / ".var/app" / prog.id
    prog.uso_conocido = True
    if not datos.is_dir():
        return  # Flatpak crea esta carpeta la primera vez que se abre la app
    fechas = []
    for d in [datos, *(h for h in datos.iterdir() if h.is_dir() and not h.is_symlink())]:
        try:
            fechas.append(d.stat().st_mtime)
            fechas += [e.stat(follow_symlinks=False).st_mtime for e in os.scandir(d)]
        except OSError:
            pass
    prog.ultimo_uso = max(fechas) if fechas else None


def _appimages(home: Path, ignorar: Horarios) -> list[Programa]:
    res = []
    for sub in CARPETAS_APPIMAGE:
        d = home / sub
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.is_file() and f.suffix.lower() == ".appimage":
                st = f.stat()
                prog = Programa(str(f), f.stem, "appimage", st.st_size, str(f).replace(str(home), "~"),
                                instalado=st.st_mtime)
                _uso_por_atime(prog, [str(f)], ignorar)
                res.append(prog)
    return res


def _steam(home: Path) -> list[Programa]:
    raiz = _raiz_steam(home)
    if not raiz:
        return []
    jugado = _ultima_vez_jugado(raiz)
    res = []
    for lib in _bibliotecas(raiz):
        for appid, d in _manifiestos(lib).items():
            nombre = d.get("name", appid)
            if nombre.startswith(HERRAMIENTAS_STEAM):
                continue
            donde = str(lib).replace(str(home), "~")
            res.append(Programa(appid, nombre, "steam", int(d.get("sizeondisk") or 0),
                                tr("juego · appid {appid} · {donde}", appid=appid, donde=donde), "",
                                {"biblioteca": str(lib), "installdir": d.get("installdir", "")},
                                ultimo_uso=jugado.get(appid), instalado=_numero(d.get("lastupdated")),
                                uso_conocido=True))
    return res


def _numero(texto) -> float | None:
    try:
        return float(texto) or None
    except (TypeError, ValueError):
        return None


def _ultima_vez_jugado(raiz: Path) -> dict[str, float]:
    """appid -> cuándo se jugó por última vez (de todas las cuentas de Steam de esta PC)."""
    res: dict[str, float] = {}
    for archivo in raiz.glob("userdata/*/config/localconfig.vdf"):
        apps = leer_vdf(archivo).get("userlocalconfigstore", {}).get("software", {}).get("valve", {}) \
            .get("steam", {}).get("apps", {})
        for appid, datos in apps.items():
            t = _numero(datos.get("lastplayed")) if isinstance(datos, dict) else None
            if t:
                res[appid] = max(res.get(appid, 0), t)
    return res


def hace(t: float | None, ahora: float | None = None) -> str:
    """'hoy', 'ayer', 'hace 5 d', 'hace 3 meses', 'hace 2 años'."""
    if t is None:
        return ""
    dias = int(((ahora or time.time()) - t) // 86400)
    if dias <= 0:
        return tr("hoy")
    if dias == 1:
        return tr("ayer")
    if dias < 60:
        return tr("hace {n} d", n=dias)
    if dias < 730:
        return tr("hace {n} meses", n=dias // 30)
    return tr("hace {n} años", n=dias // 365)
