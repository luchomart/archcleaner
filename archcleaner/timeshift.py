"""Timeshift (modo rsync): listar snapshots, medir cuánto libera borrar cada una, crear una nueva.

Las snapshots de rsync comparten los archivos que no cambiaron (hardlinks). Por eso borrar una
solo libera lo que es *exclusivo* de ella: archivos que no están en ninguna otra (st_nlink == 1).
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from .i18n import tr

RAIZ = Path("/timeshift/snapshots")
CONFIG = Path("/etc/timeshift/timeshift.json")
PREFIJO_COMENTARIO = "ArchCleaner:"

ETIQUETAS = {"ondemand": tr("manual"), "boot": tr("al arrancar"), "hourly": tr("cada hora"), "daily": tr("diaria"),
             "weekly": tr("semanal"), "monthly": tr("mensual")}


@dataclass
class Snapshot:
    nombre: str          # "2026-08-21_03-43-47" (es lo que pide `timeshift --delete --snapshot`)
    ruta: Path
    fecha: datetime
    etiquetas: list[str]
    comentario: str

    @property
    def dias(self) -> int:
        return (datetime.now() - self.fecha).days

    @property
    def tipo(self) -> str:
        return ", ".join(ETIQUETAS.get(e, e) for e in self.etiquetas) or "?"


def disponible() -> bool:
    """Timeshift instalado, configurado y en modo rsync (el modo btrfs no se maneja acá)."""
    try:
        conf = json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        return False
    return conf.get("btrfs_mode") != "true" and os.path.exists("/usr/bin/timeshift")


def listar() -> list[Snapshot]:
    """Snapshots de la más vieja a la más nueva."""
    res = []
    try:
        carpetas = [d for d in RAIZ.iterdir() if d.is_dir()]
    except OSError:
        return res
    for d in carpetas:
        try:
            info = json.loads((d / "info.json").read_text())
            fecha = datetime.fromtimestamp(int(info["created"]))
        except (OSError, ValueError, KeyError):
            try:
                fecha = datetime.strptime(d.name, "%Y-%m-%d_%H-%M-%S")
            except ValueError:
                continue
            info = {}
        etiquetas = [e for e in str(info.get("tags", "")).split() if e]
        res.append(Snapshot(d.name, d, fecha, etiquetas, str(info.get("comments", ""))))
    return sorted(res, key=lambda s: s.fecha)


def peso_exclusivo(snap: Snapshot) -> tuple[int, bool]:
    """(bytes que se liberan al borrarla, incompleto). Cuenta solo archivos sin otros hardlinks."""
    total, incompleto = 0, False
    pila = [str(snap.ruta)]
    while pila:
        carpeta = pila.pop()
        try:
            with os.scandir(carpeta) as it:
                for e in it:
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if stat.S_ISDIR(st.st_mode):
                        pila.append(e.path)
                        total += st.st_blocks * 512
                    elif st.st_nlink == 1:
                        total += st.st_blocks * 512
        except PermissionError:
            incompleto = True
        except OSError:
            pass
    return total, incompleto


def comando_borrar(snap: Snapshot) -> list[str]:
    return ["timeshift", "--delete", "--snapshot", snap.nombre, "--yes"]


def comando_crear(comentario: str) -> list[str]:
    return ["timeshift", "--create", "--comments", f"{PREFIJO_COMENTARIO} {comentario}", "--tags", "O", "--yes"]
