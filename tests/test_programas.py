"""Último uso de los programas (por atime, sin contar las lecturas de Timeshift) y cómo se ordenan."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ARCHCLEANER_LANG"] = "es"  # los tests verifican los textos en español

from archcleaner import programas
from archcleaner.programas import Programa, _uso_por_atime, hace, ordenar

DIA = 86400


class TestUltimoUso(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin = Path(self.tmp.name) / "programa"
        self.bin.write_text("#!/bin/sh\n")
        self.ahora = time.time()
        self.instalado = self.ahora - 30 * DIA
        patcher = mock.patch.object(programas, "_sin_atime", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _prog(self, atime: float, ignorar=()) -> Programa:
        os.utime(self.bin, (atime, self.instalado))
        p = Programa("x", "x", "repo", 1, instalado=self.instalado)
        _uso_por_atime(p, [str(self.bin)], list(ignorar))
        return p

    def test_usado_despues_de_instalar(self):
        p = self._prog(self.ahora - 2 * DIA)
        self.assertTrue(p.uso_conocido)
        self.assertAlmostEqual(p.ultimo_uso, self.ahora - 2 * DIA, delta=1)

    def test_no_usado_desde_que_se_instalo(self):
        p = self._prog(self.instalado + 30)  # leído durante la instalación
        self.assertTrue(p.uso_conocido)
        self.assertIsNone(p.ultimo_uso)

    def test_lectura_de_timeshift_no_cuenta(self):
        snapshot = self.ahora - 5 * DIA
        p = self._prog(snapshot + 2, ignorar=[(snapshot - 5, snapshot + 60)])
        self.assertIsNone(p.ultimo_uso, "rsync leyó el archivo durante la snapshot: eso no es usarlo")

    def test_disco_noatime_no_da_dato(self):
        with mock.patch.object(programas, "_sin_atime", return_value=True):
            p = self._prog(self.ahora - DIA)
        self.assertFalse(p.uso_conocido)


class TestOrden(unittest.TestCase):
    def setUp(self) -> None:
        ahora = time.time()
        self.lista = [
            Programa("a", "Beta", "repo", 50, ultimo_uso=ahora - DIA, instalado=ahora - 90 * DIA, uso_conocido=True),
            Programa("b", "alfa", "repo", 900, ultimo_uso=None, instalado=ahora - 60 * DIA, uso_conocido=True),
            Programa("c", "Gamma", "repo", 10, instalado=ahora - 1 * DIA),           # sin dato de uso
            Programa("d", "delta", "steam", 300, ultimo_uso=ahora - 200 * DIA, instalado=ahora - 10 * DIA,
                     uso_conocido=True),
        ]

    def nombres(self, orden: str) -> list[str]:
        return [p.nombre for p in ordenar(self.lista, orden)]

    def test_tamano(self):
        self.assertEqual(self.nombres("tamano"), ["alfa", "delta", "Beta", "Gamma"])

    def test_menos_usados_primero_y_sin_dato_al_final(self):
        self.assertEqual(self.nombres("uso"), ["delta", "alfa", "Beta", "Gamma"])

    def test_nombre_sin_importar_mayusculas(self):
        self.assertEqual(self.nombres("nombre"), ["alfa", "Beta", "delta", "Gamma"])

    def test_recien_instalados(self):
        self.assertEqual(self.nombres("reciente"), ["Gamma", "delta", "alfa", "Beta"])

    def test_orden_desconocido_es_tamano(self):
        self.assertEqual(self.nombres("cualquiera"), self.nombres("tamano"))

    def test_hace(self):
        ahora = time.time()
        self.assertEqual(hace(ahora - 100, ahora), "hoy")
        self.assertEqual(hace(ahora - 1.5 * DIA, ahora), "ayer")
        self.assertEqual(hace(ahora - 10 * DIA, ahora), "hace 10 d")
        self.assertEqual(hace(ahora - 90 * DIA, ahora), "hace 3 meses")
        self.assertEqual(hace(ahora - 800 * DIA, ahora), "hace 2 años")


if __name__ == "__main__":
    unittest.main()
