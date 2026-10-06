"""Utilidades chicas: correr comandos, formatear y parsear tamaños, leer archivos VDF de Steam."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

_ENV_C = {**os.environ, "LANG": "C", "LC_ALL": "C"}


def ejecutar(cmd: list[str], timeout: int = 120) -> str | None:
    """Corre un comando de solo lectura en inglés (para poder parsearlo). None si falla o no existe."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=_ENV_C, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 and not r.stdout:
        return None
    return r.stdout


def humano(n: int | None) -> str:
    if n is None:
        return "?"
    x = float(n)
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if abs(x) < 1024 or unidad == "TB":
            return f"{x:.0f} {unidad}" if unidad in ("B", "KB") else f"{x:.1f} {unidad}"
        x /= 1024
    return f"{n} B"


_UNIDADES = {
    "b": 1,
    "k": 1024, "kib": 1024, "m": 1024**2, "mib": 1024**2,
    "g": 1024**3, "gib": 1024**3, "t": 1024**4, "tib": 1024**4,
    # Sistema internacional (lo usa flatpak)
    "kb": 1000, "mb": 1000**2, "gb": 1000**3, "tb": 1000**4,
}


def parsear_tamano(texto: str) -> int | None:
    """'11.75 MiB', '739.5M', '1.2 GB', '1,2 GB' -> bytes."""
    m = re.search(r"([\d]+(?:[.,]\d+)?)\s*([KMGT]i?B|[kKMGT]B|[KMGT]|B)\b", texto)
    if not m:
        return None
    factor = _UNIDADES.get(m.group(2).lower())
    if factor is None:
        return None
    return int(float(m.group(1).replace(",", ".")) * factor)


def leer_vdf(ruta: Path) -> dict:
    """Parser mínimo del formato de texto VDF de Steam. Las claves quedan en minúscula."""
    try:
        texto = ruta.read_text(errors="replace")
    except OSError:
        return {}
    raiz: dict = {}
    pila = [raiz]
    clave = None
    for m in re.finditer(r'"(?P<s>(?:[^"\\]|\\.)*)"|(?P<llave>[{}])|//[^\n]*', texto):
        if m.group("llave") == "{":
            nuevo: dict = {}
            pila[-1][(clave or "").lower()] = nuevo
            pila.append(nuevo)
            clave = None
        elif m.group("llave") == "}":
            if len(pila) > 1:
                pila.pop()
        elif m.group("s") is not None:
            s = m.group("s").replace('\\"', '"').replace("\\\\", "\\")
            if clave is None:
                clave = s
            else:
                pila[-1][clave.lower()] = s
                clave = None
    return raiz


def acortar(texto: str, maximo: int) -> str:
    """Acorta por el medio: '/mnt/Datos/Games/LEGO…/pakchunk1-Windows.ucas'."""
    if len(texto) <= maximo:
        return texto
    mitad = (maximo - 1) // 2
    return texto[:mitad] + "…" + texto[-(maximo - 1 - mitad):]


def dentro_de(ruta: str, padre: str) -> bool:
    """True si `ruta` es `padre` o está adentro (comparando strings ya normalizados)."""
    return ruta == padre or ruta.startswith(padre.rstrip("/") + "/")
