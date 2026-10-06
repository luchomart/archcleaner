"""La "ficha" de un programa: todo lo que se va al desinstalarlo y todo lo que dejaría atrás.

Solo lectura. Lo que se encuentra se devuelve como Hallazgos para reusar la pantalla de selección
y el ejecutor de `limpiar` (y su seguridad).
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .detectores.steam import _tiene_partidas
from .escaner import escanear
from .modelo import Hallazgo, Item, Limpieza, Modo, Nivel, items_ordenados
from .programas import Programa
from .util import ejecutar, leer_vdf
from .i18n import tr

# Paquetes que nunca se desinstalan desde acá (ni directamente ni arrastrados por otro).
PROTEGIDOS = {
    "base", "base-devel", "linux", "linux-lts", "linux-zen", "linux-hardened", "linux-firmware",
    "linux-headers", "systemd", "systemd-libs", "pacman", "pacman-mirrorlist", "archlinux-keyring",
    "sudo", "glibc", "bash", "coreutils", "filesystem", "util-linux", "shadow", "pam",
    "grub", "efibootmgr", "mkinitcpio", "dracut", "networkmanager", "sddm",
    "plasma-desktop", "plasma-workspace", "plasma-meta", "kwin", "xorg-server", "xorg-xwayland",
    "mesa", "nvidia", "nvidia-dkms", "nvidia-open", "nvidia-open-dkms", "nvidia-utils",
    "amd-ucode", "intel-ucode", "dbus", "polkit",
    "python", "python-rich", "python-textual", "pacman-contrib", "timeshift", "glib2",
    # otros escritorios, sesiones y gestores de inicio de sesión
    "gnome-shell", "gnome-session", "mutter", "gdm", "gnome", "xfce4-session", "xfwm4", "xfce4",
    "cinnamon", "mate-session-manager", "lightdm", "ly", "greetd", "hyprland", "sway", "wayland",
    # arranque, red y sistemas de archivos
    "limine", "refind", "systemd-boot", "iwd", "dhcpcd", "wpa_supplicant", "e2fsprogs", "btrfs-progs",
    "xfsprogs", "dosfstools", "cryptsetup", "lvm2", "linux-zen-headers", "linux-lts-headers",
}
MUCHOS_PAQUETES = 15
SUFIJOS = ("-bin", "-git", "-appimage", "-stable", "-beta", "-nightly", "-debug")
# Si una carpeta tiene alguna de estas adentro, probablemente guarda partidas: nunca es "segura".
CARPETAS_PARTIDAS = {"saves", "save", "savegames", "savedgames", "worlds", "world", "players", "profiles"}

# Carpetas del sistema donde un programa suele dejar cosas que pacman no conoce.
ZONAS_RESTOS_SISTEMA = ("/etc", "/var/lib", "/var/cache", "/var/log", "/opt", "/etc/systemd/system")
# Nombres en /etc que no son de ningún paquete pero son vitales: nunca se proponen.
CRITICOS_ETC = {
    "machine-id", "hostname", "localtime", "locale.conf", "vconsole.conf", "fstab", "passwd", "shadow",
    "group", "gshadow", "sudoers", "crypttab", "mkinitcpio.conf", "resolv.conf", "hosts", "adjtime",
    "os-release", "pacman.conf", "pacman.d", "systemd", "ssl", "ca-certificates", "X11", "default",
}


@dataclass
class Servicio:
    unidad: str
    usuario: bool       # True = servicio de usuario (systemctl --user)
    activo: bool


@dataclass
class Ficha:
    programa: Programa
    bloqueo: str | None = None
    paquetes: list[Item] = field(default_factory=list)       # lo que se lleva pacman
    requerido_por: list[str] = field(default_factory=list)
    servicios: list[Servicio] = field(default_factory=list)
    comandos: list[list[str]] = field(default_factory=list)  # la desinstalación en sí
    sudo: bool = False
    claves: set[str] = field(default_factory=set)
    restos: list[Hallazgo] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def peso_total(self) -> int:
        if self.programa.origen == "appimage":
            principal = 0  # el AppImage ya está contado entre los restos
        else:
            principal = sum(i.peso or 0 for i in self.paquetes) or (self.programa.peso or 0)
        return principal + sum(h.peso or 0 for h in self.restos)


def normalizar(nombre: str) -> str:
    return re.sub(r"[^a-z0-9]", "", nombre.lower())


# ── Investigación ────────────────────────────────────────────────────────────

def investigar(prog: Programa, home: Path | None = None) -> Ficha:
    home = home or Path.home()
    ficha = Ficha(prog)
    if prog.origen in ("repo", "aur"):
        _pacman(ficha)
    elif prog.origen == "flatpak":
        _flatpak(ficha)
    elif prog.origen == "appimage":
        _appimage(ficha, home)
    elif prog.origen == "steam":
        _steam(ficha)
    if ficha.bloqueo:
        return ficha

    ficha.claves |= _claves_base(prog)
    ficha.claves = {c for c in ficha.claves if len(c) >= 3}
    otros = _nombres_de_otros(ficha)
    _restos_home(ficha, home, otros)
    if prog.origen in ("repo", "aur"):
        _restos_sistema(ficha, otros)
        _caches(ficha, home)
    for i, h in enumerate(ficha.restos, 1):
        h.numero = i
    return ficha


def _claves_base(prog: Programa) -> set[str]:
    claves = {normalizar(prog.nombre), normalizar(prog.id.rsplit("/", 1)[-1])}
    base = prog.id.rsplit("/", 1)[-1]
    for suf in SUFIJOS:
        if base.endswith(suf):
            base = base[: -len(suf)]
    claves.add(normalizar(base))
    if prog.origen == "flatpak":
        claves.add(normalizar(prog.id.rsplit(".", 1)[-1]))
    if prog.origen == "appimage":
        claves.add(normalizar(re.split(r"[-_. ]", Path(prog.id).stem)[0]))
    if prog.origen == "steam" and prog.extra.get("installdir"):
        claves.add(normalizar(prog.extra["installdir"]))
    return claves


def _pacman(ficha: Ficha) -> None:
    nombre = ficha.programa.id
    sal = subprocess.run(["pacman", "-Rs", "--print", "--print-format", "%n|%s", nombre],
                         capture_output=True, text=True, env={**os.environ, "LANG": "C"})
    if sal.returncode != 0:
        # Típicamente: otro paquete depende de este.
        info = ejecutar(["pacman", "-Qi", nombre]) or ""
        m = re.search(r"^Required By\s*:\s*(.+)$", info, re.M)
        ficha.requerido_por = [] if not m or m.group(1).strip() == "None" else m.group(1).split()
        ficha.bloqueo = tr("Otros paquetes lo necesitan: {paquetes}", paquetes=", ".join(ficha.requerido_por)) \
            if ficha.requerido_por else tr("pacman no lo puede quitar: {error}", error=sal.stderr.strip())
        return
    for linea in sal.stdout.splitlines():
        if "|" in linea:
            n, s = linea.split("|", 1)
            ficha.paquetes.append(Item(n, int(s) if s.isdigit() else None))
    nombres = {i.nombre for i in ficha.paquetes}
    if prohibidos := nombres & PROTEGIDOS:
        ficha.bloqueo = tr("Se llevaría paquetes vitales del sistema: {paquetes}", paquetes=", ".join(sorted(prohibidos)))
        return
    if len(nombres) > MUCHOS_PAQUETES:
        ficha.avisos.append(tr("Arrastra {n} paquetes: revisá bien la lista antes de confirmar.", n=len(nombres)))
    ficha.comandos = [["pacman", "-Rns", nombre]]
    ficha.sudo = True

    # Archivos del paquete principal: ejecutables, accesos directos y servicios.
    archivos = (ejecutar(["pacman", "-Qlq", *nombres]) or "").splitlines()
    propios = (ejecutar(["pacman", "-Qlq", nombre]) or "").splitlines()
    for f in propios:
        if f.startswith("/usr/bin/") and not f.endswith("/"):
            ficha.claves.add(normalizar(os.path.basename(f)))
        elif f.startswith("/usr/share/applications/") and f.endswith(".desktop"):
            base = os.path.basename(f)[: -len(".desktop")]
            ficha.claves |= {normalizar(base), normalizar(base.rsplit(".", 1)[-1])}
            if m := re.search(r"^StartupWMClass=(.+)$", _leer(f), re.M):
                ficha.claves.add(normalizar(m.group(1)))
    for f in archivos:
        for prefijo, usuario in (("/usr/lib/systemd/system/", False), ("/usr/lib/systemd/user/", True)):
            if f.startswith(prefijo) and f.endswith((".service", ".timer", ".socket")) and "@." not in f:
                _agregar_servicio(ficha, os.path.basename(f), usuario)
    # Servicios que el programa creó por su cuenta en /etc/systemd/system (ej. `nextdns install`).
    for e in _listar("/etc/systemd/system"):
        if e.endswith(".service") and normalizar(e[: -len(".service")]) in ficha.claves:
            _agregar_servicio(ficha, e, False)


def _agregar_servicio(ficha: Ficha, unidad: str, usuario: bool) -> None:
    base = ["systemctl", "--user"] if usuario else ["systemctl"]
    habilitado = (ejecutar([*base, "is-enabled", unidad]) or "").strip() in ("enabled", "enabled-runtime")
    activo = (ejecutar([*base, "is-active", unidad]) or "").strip() == "active"
    if habilitado or activo:
        ficha.servicios.append(Servicio(unidad, usuario, activo))


def _flatpak(ficha: Ficha) -> None:
    app = ficha.programa.id
    alcance = "--user" if ficha.programa.extra.get("instalacion") == "user" else "--system"
    ficha.comandos = [["flatpak", "uninstall", alcance, "--delete-data", "-y", app],
                      ["flatpak", "uninstall", alcance, "--unused", "-y"]]
    ficha.paquetes = [Item(app, ficha.programa.peso)]


def _appimage(ficha: Ficha, home: Path) -> None:
    ruta = Path(ficha.programa.id)
    # El AppImage en sí va como un "resto" seguro más: se borra con el mismo ejecutor (y su seguridad).
    ficha.restos.append(Hallazgo(
        tr("AppImage"), tr("El AppImage"), Nivel.SEGURO, ficha.programa.peso, tr("El archivo del programa."),
        rutas=[ruta], detalle=[Item(ruta.name, ficha.programa.peso, ruta)],
        limpieza=Limpieza(Modo.PAPELERA, por_item=True),
    ))


def _steam(ficha: Ficha) -> None:
    appid = ficha.programa.id
    ficha.comandos = [["xdg-open", f"steam://uninstall/{appid}"]]
    sa = Path(ficha.programa.extra["biblioteca"]) / "steamapps"
    seguros, probables = [], []
    for sub, que in (("shadercache", tr("shader cache")), ("workshop/content", tr("contenido de Workshop"))):
        d = sa / sub / appid
        if d.is_dir():
            seguros.append(Item(f"{que} ({d})", _peso(d), d))
    compat = sa / "compatdata" / appid
    if compat.is_dir() and (_peso(compat) or 0) >= 1024**2:
        marca = tr("  ⚠ puede tener partidas guardadas") if _tiene_partidas(compat) else ""
        probables.append(Item(tr("prefijo de Proton ({ruta}){marca}", ruta=compat, marca=marca), _peso(compat), compat))
    if seguros:
        ficha.restos.append(_hallazgo_restos(tr("Restos de Steam"), Nivel.SEGURO, seguros, Modo.BORRAR,
                                             tr("Shaders y Workshop del juego: se borran al desinstalar.")))
    if probables:
        ficha.restos.append(_hallazgo_restos(
            tr("Prefijo de Proton"), Nivel.REVISAR, probables, Modo.PAPELERA,
            tr("El 'Windows falso' del juego. Ahí suelen estar las PARTIDAS GUARDADAS (si el juego no usa "
              "la nube de Steam). Tildalo solo si no vas a volver a jugarlo.")))


def _nombres_de_otros(ficha: Ficha) -> set[str]:
    """Nombres que pertenecen a OTROS programas instalados: si un resto coincide, no es nuestro."""
    quitar = {i.nombre for i in ficha.paquetes}
    otros: set[str] = set()
    for linea in (ejecutar(["pacman", "-Ql"]) or "").splitlines():
        paquete, _, ruta = linea.partition(" ")
        if paquete in quitar:
            continue
        otros.add(normalizar(paquete))
        if ruta.startswith(("/usr/bin/", "/usr/share/applications/")) and not ruta.endswith("/"):
            otros.add(normalizar(os.path.basename(ruta).removesuffix(".desktop")))
    for app in (ejecutar(["flatpak", "list", "--app", "--columns=application"]) or "").split():
        if app != ficha.programa.id:
            otros.add(normalizar(app))
    return otros - ficha.claves if ficha.programa.origen != "steam" else otros


# ── Restos ───────────────────────────────────────────────────────────────────

def _certeza(nombre: str, claves: set[str]) -> str | None:
    n = normalizar(nombre.lstrip("."))
    for ext in ("conf", "json", "ini", "rc", "desktop", "png", "svg"):
        if n.endswith(ext) and n[: -len(ext)] in claves:
            return "seguro"
    if n in claves:
        return "seguro"
    if len(n) >= 5 and any(len(c) >= 5 and (n.startswith(c) or c.startswith(n)) for c in claves):
        return "probable"
    return None


def _restos_home(ficha: Ficha, home: Path, otros: set[str]) -> None:
    seguros, probables = [], []
    ignorar = {".config", ".local", ".cache", ".var", ".ssh", ".gnupg", ".steam", ".pki", ".icons", ".themes"}

    propios = {str(p) for p in carpetas_propias(home)}

    def revisar(ruta: Path) -> None:
        if ruta.name in ignorar or (ruta.is_symlink() and ruta.is_dir()) or str(ruta) in propios:
            return
        certeza = _certeza(ruta.name, ficha.claves)
        if not certeza or normalizar(ruta.name.lstrip(".")) in otros:
            return
        nombre = str(ruta).replace(str(home), "~")
        if ficha.programa.origen == "steam":
            certeza = "probable"  # en juegos, lo del home suelen ser partidas guardadas
        if _tiene_carpeta_partidas(ruta):
            certeza = "probable"
            nombre += tr("  ⚠ puede tener partidas guardadas")
        item = Item(nombre, _peso(ruta), ruta)
        (seguros if certeza == "seguro" else probables).append(item)

    for base in (home / ".config", home / ".local/share", home / ".cache", home / ".local/state", home / ".var/app"):
        for e in _listar(base):
            revisar(base / e)
    for e in _listar(home):
        if e.startswith("."):
            revisar(home / e)

    # Accesos directos y autoarranque que apuntan al programa.
    for base in (home / ".local/share/applications", home / ".config/autostart"):
        for e in _listar(base):
            if not e.endswith(".desktop"):
                continue
            f = base / e
            exec_ = re.search(r"^Exec=(\S+)", _leer(f), re.M)
            destino = exec_.group(1).strip('"') if exec_ else ""
            if (ficha.programa.origen == "appimage" and destino == ficha.programa.id) or \
                    normalizar(os.path.basename(destino)) in ficha.claves:
                if not any(i.ruta == f for i in seguros + probables):
                    seguros.append(Item(str(f).replace(str(home), "~"), _peso(f), f))

    if seguros:
        ficha.restos.append(_hallazgo_restos(
            tr("Restos en tu home (seguros)"), Nivel.SEGURO, seguros, Modo.PAPELERA,
            tr("Configuraciones, datos y caché con el nombre exacto del programa.")))
    if probables:
        ficha.restos.append(_hallazgo_restos(
            tr("Restos en tu home (probables)"), Nivel.REVISAR, probables, Modo.PAPELERA,
            tr("Se parecen al nombre del programa, pero no es seguro que sean suyos. Revisalos.")))


def _restos_sistema(ficha: Ficha, otros: set[str]) -> None:
    """Archivos/carpetas en /etc, /var/lib, etc. con el nombre del programa y que NINGÚN paquete reconoce."""
    items = []
    for zona in ZONAS_RESTOS_SISTEMA:
        for e in _listar(zona):
            ruta = Path(zona) / e
            if e in CRITICOS_ETC or ruta.is_symlink():
                continue
            nombre = e.removesuffix(".service") if zona == "/etc/systemd/system" else e
            if _certeza(nombre, ficha.claves) != "seguro" or normalizar(nombre) in otros:
                continue
            if subprocess.run(["pacman", "-Qo", str(ruta)], capture_output=True).returncode == 0:
                continue  # es de un paquete: si es del programa, lo borra pacman
            items.append(Item(str(ruta), _peso(ruta), comando=["rm", "-r", "--", str(ruta)]))
    if items:
        ficha.restos.append(_hallazgo_restos(
            tr("Restos en el sistema"), Nivel.SEGURO, items, Modo.COMANDO,
            tr("Archivos que el programa creó por su cuenta (configs, servicios, datos) y que pacman no "
              "conoce, así que no los borraría nunca."), sudo=True))


def _caches(ficha: Ficha, home: Path) -> None:
    nombres = [i.nombre for i in ficha.paquetes]
    cache = Path("/var/cache/pacman/pkg")
    items = []
    for n in nombres:
        # el paquete y su firma (.sig): pacman guarda los dos
        patron = re.compile(rf"^{re.escape(n)}-[^-]+-[^-]+-[^-]+\.pkg\.tar\.\w+(\.sig)?$")
        archivos = [cache / e for e in _listar(cache) if patron.match(e)]
        if archivos:
            versiones = sum(1 for a in archivos if not a.name.endswith(".sig"))
            items.append(Item(tr("{paquete} ({n} versiones en la caché de pacman)", paquete=n, n=versiones),
                              sum(_peso(a) or 0 for a in archivos),
                              comando=["rm", "-f", "--", *map(str, archivos)]))
    if items:
        ficha.restos.append(_hallazgo_restos(
            tr("Caché de pacman"), Nivel.SEGURO, items, Modo.COMANDO,
            tr("Los instaladores descargados de estos paquetes. Sin el programa, no sirven."), sudo=True))
    if ficha.programa.origen == "aur":
        d = home / ".cache/yay" / ficha.programa.id
        if d.is_dir():
            ficha.restos.append(_hallazgo_restos(
                tr("Caché de yay"), Nivel.SEGURO, [Item(str(d).replace(str(home), "~"), _peso(d), d)], Modo.BORRAR,
                tr("Lo que yay descargó y compiló para este paquete.")))


# ── Ayudantes ────────────────────────────────────────────────────────────────

def carpetas_propias(home: Path) -> list[Path]:
    """Lo que es de ArchCleaner mismo (su estado/log/informes y su código): nunca es un resto."""
    return [home / ".local/state/archcleaner", Path(__file__).resolve().parent.parent]


def _hallazgo_restos(titulo: str, nivel: Nivel, items: list[Item], modo: Modo, explicacion: str,
                     sudo: bool = False) -> Hallazgo:
    items = items_ordenados(items)
    texto = {Modo.BORRAR: tr("se borra"), Modo.COMANDO: tr("se borra con sudo rm")}.get(modo)
    return Hallazgo(tr("Desinstalar"), titulo, nivel, sum(i.peso or 0 for i in items), explicacion,
                    rutas=[i.ruta for i in items if i.ruta], detalle=items,
                    limpieza=Limpieza(modo, sudo=sudo, por_item=True, texto=texto))


def _tiene_carpeta_partidas(ruta: Path, profundidad: int = 3) -> bool:
    if not ruta.is_dir() or ruta.is_symlink():
        return False
    base = str(ruta).count("/")
    for raiz, dirs, _ in os.walk(ruta):
        if any(normalizar(d) in CARPETAS_PARTIDAS for d in dirs):
            return True
        if raiz.count("/") - base >= profundidad:
            dirs.clear()
    return False


def _peso(ruta: Path) -> int | None:
    try:
        if ruta.is_dir() and not ruta.is_symlink():
            return escanear(str(ruta), umbral_grande=1 << 62).peso
        return os.lstat(ruta).st_blocks * 512
    except OSError:
        return None


def _listar(carpeta: Path | str) -> list[str]:
    try:
        return sorted(os.listdir(carpeta))
    except OSError:
        return []


def _leer(ruta: Path | str) -> str:
    try:
        return Path(ruta).read_text(errors="replace")
    except OSError:
        return ""


__all__ = ["PROTEGIDOS", "Ficha", "Servicio", "investigar", "leer_vdf", "normalizar"]
