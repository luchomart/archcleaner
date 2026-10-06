"""Traducciones: todo texto marcado con tr("...") tiene que estar en inglés, con los mismos {datos}."""

from __future__ import annotations

import ast
import os
import string
import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from archcleaner.idiomas.en import TEXTOS  # noqa: E402


def _claves_del_codigo() -> dict[str, str]:
    """texto -> archivo:línea de cada tr("...") del código."""
    res: dict[str, str] = {}
    for archivo in (RAIZ / "archcleaner").rglob("*.py"):
        for n in ast.walk(ast.parse(archivo.read_text())):
            if (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "tr" and n.args
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
                res.setdefault(n.args[0].value, f"{archivo.relative_to(RAIZ)}:{n.lineno}")
    return res


def _datos(texto: str) -> set[str]:
    return {campo for _, campo, _, _ in string.Formatter().parse(texto) if campo}


class TestTraducciones(unittest.TestCase):
    def test_todo_tiene_traduccion(self):
        faltan = [f"{donde}: {texto!r}" for texto, donde in _claves_del_codigo().items() if texto not in TEXTOS]
        self.assertEqual(faltan, [], "textos sin traducir:\n" + "\n".join(faltan))

    def test_mismos_datos(self):
        distintos = [f"{texto!r}: {_datos(texto)} != {_datos(TEXTOS[texto])}"
                     for texto in _claves_del_codigo() if texto in TEXTOS and _datos(texto) != _datos(TEXTOS[texto])]
        self.assertEqual(distintos, [], "\n".join(distintos))

    def test_no_sobran_traducciones(self):
        codigo = _claves_del_codigo()
        # nombres de detectores y motivos se traducen con tr(variable): están en el diccionario igual
        dinamicos = {"Sistema", "Pacman", "AUR", "Flatpak", "Steam", "Desarrollo", "Home", "Archivos gigantes"}
        sobran = sorted(k for k in TEXTOS if k not in codigo and k not in dinamicos)
        self.assertEqual(sobran, [], "traducciones que ya no se usan:\n" + "\n".join(sobran))

    def test_la_app_arranca_en_ingles(self):
        env = {**os.environ, "ARCHCLEANER_LANG": "en"}
        sal = subprocess.run([sys.executable, str(RAIZ / "archcleaner.py"), "--help"], capture_output=True,
                             text=True, env=env)
        self.assertEqual(sal.returncode, 0, sal.stderr)
        self.assertIn("disk", sal.stdout.lower())


if __name__ == "__main__":
    unittest.main()
