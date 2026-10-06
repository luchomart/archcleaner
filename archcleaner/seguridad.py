"""Última barrera antes de borrar: cada ruta se verifica acá, sin importar qué detector la propuso.

Reglas:
- Solo se toca lo que está dentro de una "zona permitida" (tu home, discos en /mnt y /media,
  y unas pocas carpetas del sistema puntuales).
- Nunca se toca la raíz de una zona, un punto de montaje, ni tus carpetas personales
  (Documentos, Imágenes...) en sí.
- Los enlaces simbólicos se tratan como enlaces: se borra el enlace, nunca a dónde apunta.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .util import dentro_de, ejecutar
from .i18n import tr

# Carpetas del sistema donde sí se puede borrar algo adentro.
ZONAS_SISTEMA = (
    "/var/cache/pacman/pkg",
    "/var/lib/systemd/coredump",
    "/usr/lib/modules",
)
ZONAS_DISCOS = ("/mnt", "/media", "/run/media")
# Restos que deja un programa desinstalado: solo cosas DIRECTAMENTE adentro de estas carpetas,
# que no sean de ningún paquete y que no estén en la lista de críticos.
ZONAS_RESTOS = ("/etc", "/var/lib", "/var/cache", "/var/log", "/opt", "/etc/systemd/system")

PROHIBIDAS = {
    "/", "/bin", "/boot", "/dev", "/efi", "/etc", "/home", "/lib", "/lib64", "/mnt", "/media",
    "/opt", "/proc", "/root", "/run", "/run/media", "/sbin", "/srv", "/sys", "/tmp", "/usr", "/var",
    "/timeshift",
}

YA_NO_EXISTE = tr("ya no existe")  # se compara: por eso es una constante

VACIABLES = (".cache", ".local/share/Trash")  # carpetas protegidas cuyo CONTENIDO sí se puede vaciar

XDG_PERSONALES = ("DESKTOP", "DOCUMENTS", "DOWNLOAD", "MUSIC", "PICTURES", "PUBLICSHARE", "TEMPLATES", "VIDEOS")


def _carpetas_personales(home: Path) -> set[str]:
    res = {str(home)}
    for clave in XDG_PERSONALES:
        ruta = (ejecutar(["xdg-user-dir", clave]) or "").strip()
        if ruta and ruta != str(home):
            res.add(ruta)
    for sub in (".config", ".local", ".local/share", ".local/state", ".cache", ".ssh", ".gnupg", ".var",
                ".var/app", ".steam", ".local/share/Steam", ".local/share/Trash"):
        res.add(str(home / sub))
    return res


class Verificador:
    def __init__(self, home: Path | None = None):
        self.home = home or Path.home()
        self.personales = _carpetas_personales(self.home)
        self.vaciables = {str(self.home / v) for v in VACIABLES}
        self.propias = [self.home / ".local/state/archcleaner", Path(__file__).resolve().parent.parent]
        self.kernel_actual = os.uname().release

    def problema(self, ruta: Path | str, vaciar: bool = False) -> str | None:
        """None si se puede borrar; si no, el motivo.

        `vaciar=True` pregunta si se puede borrar *el contenido* de la carpeta. De las carpetas
        protegidas, solo se pueden vaciar las de VACIABLES (caché y papelera); lo de adentro
        se verifica aparte, cosa por cosa.
        """
        s = os.path.normpath(os.path.abspath(str(ruta)))
        p = Path(s)
        if not p.exists() and not p.is_symlink():
            return YA_NO_EXISTE
        # Si alguna carpeta del camino es un enlace (ej. ~/enlace -> /etc), lo que se borra de verdad
        # está en otro lado: se verifica también la ruta real (el último elemento no se resuelve:
        # si es un enlace, se borra el enlace).
        real = os.path.join(os.path.realpath(os.path.dirname(s)), os.path.basename(s))
        if real != s and (motivo := self.problema(real, vaciar)):
            return tr("{motivo} (la ruta pasa por un enlace a {destino})", motivo=motivo,
                     destino=os.path.dirname(real))
        if s in PROHIBIDAS:
            return tr("carpeta del sistema protegida")
        if any(dentro_de(s, str(p)) for p in self.propias):
            return tr("son datos o código del propio ArchCleaner")
        if s in self.personales and not (vaciar and s in self.vaciables):
            return tr("carpeta personal protegida (se puede borrar lo de adentro, no la carpeta)")
        if not p.is_symlink() and os.path.ismount(s):
            return tr("es un punto de montaje (un disco entero)")

        en_home = dentro_de(s, str(self.home))
        en_disco = any(dentro_de(s, z) for z in ZONAS_DISCOS) and s.count("/") >= 3
        en_sistema = any(dentro_de(s, z) and s != z for z in ZONAS_SISTEMA)
        if not (en_home or en_disco or en_sistema) and os.path.dirname(s) in ZONAS_RESTOS:
            return self._problema_resto(p)
        if not (en_home or en_disco or en_sistema):
            return tr("fuera de las zonas donde ArchCleaner puede borrar")
        if dentro_de(s, "/usr/lib/modules") and (p.name == self.kernel_actual or s.count("/") != 4):
            return tr("módulos del kernel que estás usando")
        return None

    @staticmethod
    def _problema_resto(p: Path) -> str | None:
        """Un resto de programa en /etc, /var/lib, etc.: solo si ningún paquete lo reconoce."""
        from .ficha import CRITICOS_ETC  # import tardío: ficha importa cosas pesadas

        if p.name in CRITICOS_ETC or str(p) in PROHIBIDAS:
            return tr("archivo vital del sistema")
        if subprocess.run(["pacman", "-Qo", str(p)], capture_output=True).returncode == 0:
            return tr("pertenece a un paquete instalado (lo maneja pacman)")
        if p.is_dir() and not p.is_symlink() and (ajeno := _archivo_de_paquete_adentro(p)):
            return tr("adentro hay un archivo de un paquete instalado ({archivo})", archivo=ajeno)
        return None


def _archivo_de_paquete_adentro(carpeta: Path, maximo: int = 5000) -> str | None:
    """¿Algún archivo de adentro pertenece a un paquete? (una carpeta "huérfana" puede tener archivos ajenos)."""
    archivos: list[str] = []
    for raiz, _dirs, nombres in os.walk(carpeta):
        archivos += [os.path.join(raiz, n) for n in nombres]
        if len(archivos) >= maximo:
            return tr("tiene más de {n} archivos: revisalo a mano", n=maximo)
    for i in range(0, len(archivos), 500):
        sal = subprocess.run(["pacman", "-Qo", *archivos[i:i + 500]], capture_output=True, text=True,
                             env={**os.environ, "LANG": "C"})
        for linea in sal.stdout.splitlines():
            if " is owned by " in linea:
                return linea.split(" is owned by ")[0]
    return None
