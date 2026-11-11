"""🙈 "No mostrar más": lo oculto deja de proponerse para borrar, y nunca se borra "por la puerta de atrás".

Lo importante: si algo oculto queda ADENTRO de una ruta que un hallazgo borra entera (o con un comando),
ese hallazgo no puede seguir proponiéndose: pasa a ser informativo.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ARCHCLEANER_LANG"] = "es"

from test_tui import TAMANO, BaseTUI

from archcleaner import estado, ignorados
from archcleaner.modelo import Hallazgo, Item, Limpieza, Modo, Nivel
from archcleaner.tui.app import ArchCleanerApp


def _por_item(*rutas: str) -> Hallazgo:
    items = [Item(os.path.basename(r), 100, Path(r)) for r in rutas]
    return Hallazgo("Archivos", "Archivos gigantes", Nivel.REVISAR, 100 * len(rutas), "",
                    rutas=[Path(r) for r in rutas], detalle=items, limpieza=Limpieza(Modo.PAPELERA, por_item=True))


def _entero(*rutas: str, modo: Modo = Modo.VACIAR) -> Hallazgo:
    return Hallazgo("Pacman", "Caché", Nivel.SEGURO, 500, "Se regenera.", rutas=[Path(r) for r in rutas],
                    limpieza=Limpieza(modo, comandos=[["paccache", "-rk1"]] if modo == Modo.COMANDO else []))


class TestAplicar(unittest.TestCase):
    def test_saca_items_ocultos_y_descuenta_el_peso(self):
        h = _por_item("/d/ollama/blobs/a", "/d/ollama/blobs/b", "/d/video.mkv")
        lista = ignorados.aplicar([h], ["/d/ollama"])  # ocultar la carpeta oculta lo de adentro
        self.assertEqual(lista, [h])
        self.assertEqual([it.nombre for it in h.detalle], ["video.mkv"])
        self.assertEqual(h.peso, 100)

    def test_si_no_queda_nada_el_hallazgo_desaparece(self):
        self.assertEqual(ignorados.aplicar([_por_item("/d/a", "/d/b")], ["/d"]), [])

    def test_item_que_tiene_algo_oculto_adentro_tambien_sale(self):
        h = _por_item("/d/juego", "/d/otro")
        ignorados.aplicar([h], ["/d/juego/saves"])  # borrar /d/juego borraría las partidas ocultas
        self.assertEqual([it.nombre for it in h.detalle], ["otro"])

    def test_hallazgo_entero_oculto_desaparece(self):
        self.assertEqual(ignorados.aplicar([_entero("/c/yay")], ["/c/yay"]), [])

    def test_algo_oculto_adentro_de_un_hallazgo_entero_lo_vuelve_informativo(self):
        h = _entero("/c/yay")
        ignorados.aplicar([h], ["/c/yay/paquete-que-quiero"])  # VACIAR /c/yay lo borraría igual
        self.assertIsNone(h.limpieza)
        self.assertEqual(h.nivel, Nivel.INFO)
        self.assertIn("/c/yay/paquete-que-quiero", h.explicacion)

    def test_comando_con_una_ruta_oculta_a_medias_queda_informativo(self):
        h = _entero("/var/cache/pacman/pkg", "/otra", modo=Modo.COMANDO)
        ignorados.aplicar([h], ["/var/cache/pacman/pkg"])
        self.assertIsNone(h.limpieza)

    def test_rutas_parecidas_no_cuentan(self):
        h = _por_item("/d/ollama-viejo", "/d/ollama")
        ignorados.aplicar([h], ["/d/ollama"])
        self.assertEqual([it.nombre for it in h.detalle], ["ollama-viejo"])

    def test_los_informativos_no_se_tocan(self):
        h = Hallazgo("Steam", "Juego", Nivel.INFO, 10, "", rutas=[Path("/s/juego")])
        self.assertEqual(ignorados.aplicar([h], ["/s"]), [h])


class TestGuardar(unittest.TestCase):
    def setUp(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        p = mock.patch.object(estado, "ARCHIVO", tmp / "estado.json")
        p.start()
        self.addCleanup(p.stop)

    def test_ocultar_y_volver_a_mostrar(self):
        ignorados.ocultar(["/d/ollama/", "/d/ollama", "/d/b"], que="Archivos gigantes")
        self.assertEqual(sorted(ignorados.rutas()), ["/d/b", "/d/ollama"])  # sin repetidos ni "/" final
        self.assertEqual(ignorados.oculta("/d/ollama/blobs/x"), "/d/ollama")
        ignorados.mostrar(["/d/ollama"])
        self.assertEqual(ignorados.rutas(), ["/d/b"])
        self.assertIsNone(ignorados.oculta("/d/ollama/blobs/x"))

    def test_otras_cosas_del_estado_no_se_pierden(self):
        estado.guardar_preferencia("orden", "peso")
        ignorados.ocultar(["/d/a"])
        self.assertEqual(estado.leer()["preferencias"], {"orden": "peso"})


class TestPantalla(BaseTUI):
    async def test_ocultar_desde_la_lista_no_lo_borra_y_se_puede_recuperar(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            await self.esperar(app, "MenuScreen")
            await pilot.press("l")
            await self.esperar(app, "SeleccionScreen")
            pantalla = app.screen
            self.assertFalse(pantalla.query_one("#ocultos").display)  # sin nada oculto, no hay botón
            lista = pantalla.query_one("OptionList")
            lista.highlighted = next(i for i, o in enumerate(lista.options) if o.id == "h2-0")  # el video
            await pilot.press("i")
            await self.esperar(app, "Dialogo")
            await pilot.click("#si")
            await self.esperar(app, "SeleccionScreen")
            self.assertTrue(await self.esperar_que(lambda: not any(o.id == "h2-0" for o in lista.options)))
            self.assertEqual(pantalla.marcados, {"h1"})  # la caché 🟢 sigue tildada
            self.assertIn(str(self.video), ignorados.rutas())
            self.assertTrue(pantalla.query_one("#ocultos").display)

            await pilot.click("#ocultos")
            await self.esperar(app, "Ocultos")
            await pilot.click("#o0")
            await pilot.click("#mostrar")
            await self.esperar(app, "SeleccionScreen")
            self.assertEqual(ignorados.rutas(), [])

            await pilot.click("#continuar")
            await self.esperar(app, "PlanScreen")
            await pilot.click("#ejecutar")
            await self.esperar_fin(app)
        self.assertFalse(self.cache.exists())
        self.assertTrue(self.video.exists(), "lo oculto no se toca")

    async def test_explorar_oculta_y_vuelve_a_mostrar_con_i(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            app.flujo_explorar(str(self.home / "Videos"))
            await self.esperar(app, "ExplorarScreen")
            await pilot.pause()
            await pilot.press("i")
            await self.esperar(app, "Dialogo")
            await pilot.click("#si")
            await self.esperar(app, "ExplorarScreen")
            self.assertTrue(await self.esperar_que(lambda: ignorados.rutas() == [str(self.video)]))
            self.assertFalse(any(h.titulo == "Archivos gigantes" for h in app.resultado.hallazgos))
            self.assertIn("🙈", str(app.screen.query_one("OptionList").get_option_at_index(0).prompt))
            await pilot.press("i")  # ya oculto: lo vuelve a mostrar (sin preguntar: no borra nada)
            self.assertTrue(await self.esperar_que(lambda: ignorados.rutas() == []))
        self.assertTrue(self.video.exists())


if __name__ == "__main__":
    unittest.main()
