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



QEI = """Name            : plasma-pa
Version         : 6.5.0-1
Description     : Plasma applet for audio volume management using PulseAudio
Groups          : plasma
Required By     : None
Optional For    : plasma-desktop
Installed Size  : 1024.00 KiB
Install Date    : Mon 03 Nov 2026 10:00:00 AM -03

Name            : qt6-base
Version         : 6.10.0-1
Description     : A cross-platform application and UI framework
Groups          : None
Required By     : ark  dolphin  kate
Optional For    : None
Installed Size  : 70.00 MiB
Install Date    : Mon 03 Nov 2026 10:00:00 AM -03

"""


class TestPacman(unittest.TestCase):
    def test_lee_grupos_requeridos_y_opcionales(self):
        def ejecutar(cmd, timeout=120):
            return QEI if cmd[:2] == ["pacman", "-Qei"] else ""
        with mock.patch.object(programas, "ejecutar", side_effect=ejecutar):
            leidos = {p.id: p for p in programas._pacman([])}
        self.assertEqual(leidos["plasma-pa"].grupos, ["plasma"])
        self.assertEqual(leidos["plasma-pa"].requerido_por, [])
        self.assertEqual(leidos["plasma-pa"].opcional_para, ["plasma-desktop"])
        self.assertEqual(leidos["qt6-base"].grupos, [])
        self.assertEqual(leidos["qt6-base"].requerido_por, ["ark", "dolphin", "kate"])


class TestSemaforo(unittest.TestCase):
    """🟢 🟡 🔴 de la lista de Desinstalar: sale de datos reales, no de la IA."""

    @staticmethod
    def color(id_: str, origen: str = "repo", **extra) -> str:
        from archcleaner.ficha import semaforo
        return semaforo(Programa(id_, extra.pop("nombre", id_), origen, 1, **extra))[0]

    def test_rojo_si_es_vital_o_lo_necesitan_otros(self):
        self.assertEqual(self.color("systemd"), "rojo")
        self.assertEqual(self.color("qt6-base", requerido_por=["dolphin"]), "rojo")
        self.assertEqual(self.color("linux", "aur"), "rojo")

    def test_amarillo_escritorio_drivers_y_herramientas_de_steam(self):
        self.assertEqual(self.color("plasma-pa", grupos=["plasma"]), "amarillo")
        self.assertEqual(self.color("vulkan-radeon"), "amarillo")
        self.assertEqual(self.color("xf86-video-amdgpu", grupos=["xorg-drivers"]), "amarillo")
        self.assertEqual(self.color("sof-firmware"), "amarillo")
        self.assertEqual(self.color("1493710", "steam", nombre="Proton Experimental"), "amarillo")

    def test_verde_lo_demas(self):
        self.assertEqual(self.color("gimp"), "verde")
        self.assertEqual(self.color("unrar", opcional_para=["ark"]), "verde")  # opcional: la ficha avisa
        self.assertEqual(self.color("kate", grupos=["kde-applications"]), "verde")
        self.assertEqual(self.color("org.gimp.GIMP", "flatpak"), "verde")
        self.assertEqual(self.color("570", "steam", nombre="Dota 2"), "verde")

    def test_un_flatpak_no_es_vital_aunque_se_llame_igual(self):
        self.assertEqual(self.color("systemd", "flatpak"), "verde")

    def test_la_ficha_avisa_si_no_es_recomendado(self):
        from archcleaner import ficha
        prog = Programa("/tmp/no-existe/Algo.AppImage", "Algo", "appimage", 1)
        with mock.patch.object(ficha, "semaforo", return_value=("amarillo", "Motivo de prueba.")), \
                mock.patch.object(ficha, "_appimage"), mock.patch.object(ficha, "_restos_home"), \
                tempfile.TemporaryDirectory() as home:
            f = ficha.investigar(prog, Path(home))
        self.assertIn("No recomendado. Motivo de prueba.", f.avisos)


if __name__ == "__main__":
    unittest.main()
