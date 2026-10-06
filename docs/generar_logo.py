"""Genera el logo y la imagen para compartir del repo (necesita rsvg-convert, de librsvg).

    python docs/generar_logo.py

- docs/logo.svg            el logo (baldosa con el anillo del disco)
- docs/social-preview.png  1280x640, la tarjeta que muestran Reddit/Discord/etc. al pegar el link
                           (se sube a mano: Settings → General → Social preview)

El anillo es un disco con los tres niveles de la app (🟢 seguro, 🟡 revisar, 🔵 info); el tramo verde
(la basura) sale volando convertido en destellos.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

DOCS = Path(__file__).resolve().parent
VERDE, AMARILLO, AZUL = "#22c55e", "#f59e0b", "#3b82f6"
BALDOSA, BLANCO, FONDO = "#1e293b", "#f8fafc", "#0d1117"


def _arco(cx: float, cy: float, r: float, a0: float, a1: float, color: str, ancho: float) -> str:
    """Arco de a0 a a1 (en % de vuelta, 0 = arriba, sentido horario)."""
    def punto(a: float) -> tuple[float, float]:
        t = math.radians(a * 3.6 - 90)
        return cx + r * math.cos(t), cy + r * math.sin(t)
    (x0, y0), (x1, y1) = punto(a0), punto(a1)
    grande = 1 if a1 - a0 > 50 else 0
    return (f'<path d="M{x0:.2f} {y0:.2f} A{r} {r} 0 {grande} 1 {x1:.2f} {y1:.2f}" fill="none" '
            f'stroke="{color}" stroke-width="{ancho}" stroke-linecap="round"/>')


def _destello(cx: float, cy: float, s: float, color: str) -> str:
    k = s * 0.18
    return (f'<path d="M{cx} {cy - s} C{cx + k} {cy - k} {cx + k} {cy - k} {cx + s} {cy} '
            f'C{cx + k} {cy + k} {cx + k} {cy + k} {cx} {cy + s} C{cx - k} {cy + k} {cx - k} {cy + k} {cx - s} {cy} '
            f'C{cx - k} {cy - k} {cx - k} {cy - k} {cx} {cy - s}Z" fill="{color}"/>')


def logo() -> str:
    """El logo en un lienzo de 256x256."""
    return "".join([
        f'<rect x="8" y="8" width="240" height="240" rx="56" fill="{BALDOSA}"/>',
        _arco(128, 128, 70, 30, 72, AMARILLO, 26),
        _arco(128, 128, 70, 80, 98, AZUL, 26),
        _arco(128, 128, 70, 2, 22, VERDE, 26),
        _destello(186, 52, 16, VERDE),
        _destello(212, 88, 9, VERDE),
        f'<circle cx="160" cy="34" r="5" fill="{VERDE}"/>',
        _destello(128, 128, 26, BLANCO),
    ])


def _svg(contenido: str, ancho: int, alto: int) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
            f'viewBox="0 0 {ancho} {alto}">{contenido}</svg>\n')


def _texto(x: float, y: float, texto: str, tam: int, color: str, negrita: bool = False) -> str:
    peso = ' font-weight="bold"' if negrita else ""
    return (f'<text x="{x}" y="{y}" font-family="Noto Sans, sans-serif" font-size="{tam}"{peso} '
            f'fill="{color}">{texto}</text>')


def social() -> str:
    """Tarjeta de 1280x640: logo a la izquierda, nombre y lema a la derecha."""
    niveles = ""
    x = 520
    for color, nombre in ((VERDE, "safe junk"), (AMARILLO, "review"), (AZUL, "info")):
        niveles += f'<circle cx="{x + 11}" cy="458" r="11" fill="{color}"/>' + _texto(x + 32, 468, nombre, 30, "#cbd5e1")
        x += 62 + len(nombre) * 15
    return _svg("".join([
        f'<rect width="1280" height="640" fill="{FONDO}"/>',
        f'<g transform="translate(130,180) scale(1.11)">{logo()}</g>',
        _texto(520, 290, "ArchCleaner", 96, BLANCO, negrita=True),
        _texto(522, 352, "Disk analyzer, cleaner and trace-free", 36, "#94a3b8"),
        _texto(522, 398, "uninstaller for Arch Linux", 36, "#94a3b8"),
        niveles,
    ]), 1280, 640)


def main() -> None:
    (DOCS / "logo.svg").write_text(_svg(logo(), 256, 256))
    tmp = DOCS / "social-preview.svg"
    tmp.write_text(social())
    subprocess.run(["rsvg-convert", str(tmp), "-o", str(DOCS / "social-preview.png")], check=True)
    tmp.unlink()
    print("docs/logo.svg y docs/social-preview.png listos")


if __name__ == "__main__":
    main()
