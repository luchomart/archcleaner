"""Historial: fotos del disco, cuáles se guardan y qué creció entre dos."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ARCHCLEANER_LANG"] = "es"  # los tests verifican los textos en español

from archcleaner import estado, historial
from archcleaner.historial import DIA, Foto, comparar, culpables, que_borrar

GB, MB = 1024**3, 1024**2
H = "/home/u"


def foto(dias_atras: float, carpetas: dict[str, int], libre: int = 50 * GB) -> Foto:
    return Foto(time.time() - dias_atras * DIA, [H, "/"], carpetas, {"/": [100 * GB, libre]})


class TestPoda(unittest.TestCase):
    def test_semana_completa_una_por_semana_y_una_por_mes(self):
        ahora = datetime(2026, 10, 5, 12).timestamp()
        fechas = [ahora - d * DIA - h * 3600 for d in range(200) for h in (0, 5)]  # dos por día, 200 días
        quedan = sorted(set(fechas) - set(que_borrar(fechas, ahora)))
        recientes = [f for f in quedan if ahora - f < 7 * DIA]
        self.assertEqual(len(recientes), 14, "de la última semana quedan todas")
        semanales = [f for f in quedan if 7 * DIA <= ahora - f < 90 * DIA]
        self.assertLessEqual(len(semanales), 13)
        mensuales = [f for f in quedan if ahora - f >= 90 * DIA]
        self.assertLessEqual(len(mensuales), 5)
        self.assertIn(max(fechas), quedan)

    def test_guardar_poda_y_vuelve_a_leer(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(estado, "ARCHIVO", Path(d) / "estado.json"):
            for dias in (100, 99, 98, 2, 1):
                historial.guardar(foto(dias, {H: dias * GB}))
            fotos = historial.listar()
            self.assertEqual(len(fotos), 3, "las de hace 98-100 días son del mismo mes: queda una")
            ultima = historial.ultima()
            self.assertEqual(ultima.carpetas[H], 1 * GB)
            self.assertEqual(historial.anterior(ultima.fecha).carpetas[H], 2 * GB)
            self.assertEqual(historial.anterior(ultima.fecha, dias=30).carpetas[H], 98 * GB)
            self.assertEqual(historial.anterior(ultima.fecha, dias=500).carpetas[H], 98 * GB,
                             "si no hay tan vieja, la más vieja que haya")


class TestComparar(unittest.TestCase):
    def setUp(self) -> None:
        self.antes = foto(3, {H: 10 * GB, f"{H}/.cache": 1 * GB, f"{H}/.local": 3 * GB,
                              f"{H}/.local/share": 3 * GB, f"{H}/.local/share/Steam": 2 * GB,
                              f"{H}/Videos": 500 * MB, "/": 20 * GB, "/var": 2 * GB, "/var/cache": 1 * GB,
                              "/home": 1 * MB}, libre=30 * GB)
        self.despues = foto(0, {H: 13 * GB, f"{H}/.cache": 2 * GB, f"{H}/.cache/yay": 900 * MB,
                                f"{H}/.local": 5 * GB, f"{H}/.local/share": 5 * GB,
                                f"{H}/.local/share/Steam": 4 * GB, "/": 21 * GB, "/var": 3 * GB,
                                "/var/cache": 2 * GB, "/home": 1 * MB}, libre=26 * GB)
        self.comp = comparar(self.antes, self.despues)

    def test_apunta_a_la_carpeta_culpable(self):
        top = dict(culpables(self.comp))
        self.assertEqual(top.get(f"{H}/.local/share/Steam"), 2 * GB, "no «.local», sino adentro")
        self.assertIn("/var/cache", top)

    def test_nuevas_y_borradas(self):
        self.assertEqual(self.comp.nuevas, {f"{H}/.cache/yay"})
        self.assertEqual(self.comp.borradas, {f"{H}/Videos"})

    def test_la_raiz_no_se_repite_y_el_home_no_cuenta_dos_veces(self):
        raiz = next(n for n in self.comp.crecio if n.ruta == "/")
        rutas = []

        def juntar(n):
            for h in n.hijos:
                rutas.append(h.ruta)
                juntar(h)
        juntar(raiz)
        self.assertNotIn("/", rutas)
        self.assertFalse(any(r.startswith(H) for r in rutas), "el home tiene su propio árbol")

    def test_paneles_se_dibujan(self):
        from rich.console import Console
        consola = Console(width=100, record=True, file=io.StringIO())
        consola.print(*historial.paneles(self.comp), historial.panel_resumen(self.comp))
        texto = consola.export_text()
        self.assertIn(".local/share/Steam", texto)
        self.assertIn("−4.0 GB", texto)

    def test_chispa(self):
        self.assertEqual(historial.chispa([1, 2, 3]), "▁▅█")
        self.assertEqual(historial.chispa([5, 5]), "▄▄")


if __name__ == "__main__":
    unittest.main()
