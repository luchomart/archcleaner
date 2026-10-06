"""La barra de avance del análisis y los tiempos que guarda para estimarla."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from archcleaner import estado
from archcleaner.analisis import _Barra
from archcleaner.detectores import DETECTORES


class TestBarra(unittest.TestCase):
    def test_nunca_retrocede_ni_llega_al_100_antes_de_tiempo(self):
        vistos = []
        b = _Barra(["/a", "/b"], {}, "/a", lambda f, e, d: vistos.append(f))
        b.dentro(b.parte["/a"], 0.5, "x")
        b.dentro(b.parte["/a"], 0.2, "x")   # un dato que tiraría para atrás
        b.dentro(b.parte["/a"], 5.0, "x")   # más bytes de los esperados
        b.hecho = 1.0
        b.mostrar(1.0, "x")
        self.assertEqual(vistos, sorted(vistos))
        self.assertLessEqual(max(vistos), 0.99)

    def test_reparte_segun_lo_que_tardo_cada_parte(self):
        previos = {"raices": {"/lento": {"segundos": 9}, "/rapido": {"segundos": 1}},
                   "detectores": {n: 0 for n, _ in DETECTORES}}
        b = _Barra(["/lento", "/rapido"], previos, "/x", None)
        self.assertGreater(b.parte["/lento"], b.parte["/rapido"] * 5)
        self.assertAlmostEqual(sum(b.parte.values()) + sum(b.parte_detector.values()), 1.0)

    def test_sin_datos_previos_tambien_suma_uno(self):
        b = _Barra(["/a"], {"detectores": 3.5}, "/a", None)  # formato viejo: un solo número
        self.assertAlmostEqual(sum(b.parte.values()) + sum(b.parte_detector.values()), 1.0)


class TestTiempos(unittest.TestCase):
    def test_analisis_rapido_no_borra_los_discos(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(estado, "ARCHIVO", Path(d) / "estado.json"):
            estado.guardar_tiempos({"raices": {"/mnt/Datos": {"bytes": 5, "segundos": 2}}, "detectores": {"A": 1}})
            estado.guardar_tiempos({"raices": {}, "detectores": {"A": 9}})   # --rapido
            t = estado.tiempos_previos()
            self.assertIn("/mnt/Datos", t["raices"])
            self.assertEqual(t["detectores"], {"A": 1})


if __name__ == "__main__":
    unittest.main()
