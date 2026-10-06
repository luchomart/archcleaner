"""Detectores de basura. Cada módulo expone `detectar(ctx) -> list[Hallazgo]`.

El orden importa: `home` y `grandes` van al final para no contar dos veces lo que ya
reportaron los demás.
"""

from . import aur, desarrollo, flatpak, grandes, home, pacman, sistema, steam

DETECTORES = [
    ("Sistema", sistema),
    ("Pacman", pacman),
    ("AUR", aur),
    ("Flatpak", flatpak),
    ("Steam", steam),
    ("Desarrollo", desarrollo),
    ("Home", home),
    ("Archivos gigantes", grandes),
]
