"""Tests de la app (textual): se maneja con clics y teclas como lo haría una persona.

Todo corre en un home FALSO dentro de una carpeta temporal: los archivos que se borran son de
prueba, la papelera es la del home falso y el log/estado de ArchCleaner van ahí también. El
análisis y la lista de programas son inventados, así que no se escanea ni se toca nada real.

    python -m unittest discover tests
"""

from __future__ import annotations

import asyncio
import io
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ARCHCLEANER_LANG"] = "es"  # los tests verifican los textos en español

from archcleaner import acciones, estado, informe
from archcleaner.analisis import Resultado
from archcleaner.contexto import Contexto
from archcleaner.escaner import escanear
from archcleaner.modelo import Hallazgo, Item, Limpieza, Modo, Nivel
from archcleaner.programas import Programa
from archcleaner.tui import app as appmod
from archcleaner.tui.app import ArchCleanerApp

TAMANO = (110, 36)


def _archivo(ruta: Path, kb: int) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(os.urandom(kb * 1024))
    return ruta


class BaseTUI(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="archcleaner-test-"))
        self.home = self.tmp / "home"
        h = self.home
        self.cache = _archivo(h / ".cache/prueba/basura.bin", 100).parent
        self.video = _archivo(h / "Videos/viejo.mkv", 300)
        _archivo(h / "Juegos/grande/datos.pak", 200)
        _archivo(h / "Juegos/chico.txt", 4)
        self.appimage = _archivo(h / "Aplicaciones/Zzprueba.AppImage", 50)
        _archivo(h / ".config/Zzprueba/config.ini", 4)
        self.papelera = h / ".local/share/Trash/files"

        entorno = {"HOME": str(h), "XDG_DATA_HOME": str(h / ".local/share"),
                   "XDG_CONFIG_HOME": str(h / ".config"), "XDG_CACHE_HOME": str(h / ".cache")}
        estado_dir = h / ".local/state/archcleaner"
        self.parches = [
            mock.patch.dict(os.environ, entorno),
            mock.patch.object(estado, "ARCHIVO", estado_dir / "estado.json"),
            mock.patch.object(estado, "LOG", estado_dir / "acciones.log"),
            mock.patch.object(acciones, "LOG", estado_dir / "acciones.log"),
            mock.patch.object(informe, "CARPETA_INFORMES", estado_dir / "informes"),
            mock.patch.object(appmod, "analizar", side_effect=lambda *a, **k: self._resultado()),
            mock.patch.object(appmod, "listar", side_effect=lambda *a, **k: self._programas()),
        ]
        for p in self.parches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(self.parches)])
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    async def asyncSetUp(self) -> None:
        asyncio.get_running_loop().set_debug(False)  # el modo debug avisa de cada pantalla que tarda >0.1 s

    # ── datos inventados ──

    def _resultado(self) -> Resultado:
        ctx = Contexto(home=self.home)
        ctx.escaneos = [escanear(str(self.home), [], 1 << 40)]
        hallazgos = []
        if self.cache.exists():
            hallazgos.append(Hallazgo(
                "Home", "Caché de prueba", Nivel.SEGURO, 100 * 1024, "Se regenera sola.",
                rutas=[self.cache], limpieza=Limpieza(Modo.BORRAR)))
        if self.video.exists():
            hallazgos.append(Hallazgo(
                "Archivos", "Archivos gigantes", Nivel.REVISAR, 300 * 1024, "Fijate si lo querés.",
                rutas=[self.video], detalle=[Item("viejo.mkv", 300 * 1024, self.video)], suma=False,
                limpieza=Limpieza(Modo.PAPELERA, por_item=True)))
        for i, h in enumerate(hallazgos, 1):
            h.numero = i
        return Resultado(ctx, hallazgos)

    def _programas(self) -> list[Programa]:
        return [Programa(str(self.appimage), "Zzprueba", "appimage", 50 * 1024, "programa de prueba")]

    # ── manejo de la app ──

    async def esperar(self, app: ArchCleanerApp, tipo: str, seg: float = 15) -> None:
        for _ in range(int(seg * 20)):
            if type(app.screen).__name__ == tipo:
                await asyncio.sleep(0.05)
                return
            await asyncio.sleep(0.05)
        self.fail(f"esperaba la pantalla {tipo}, estoy en {type(app.screen).__name__}")

    async def esperar_fin(self, app: ArchCleanerApp, seg: float = 15) -> None:
        await self.esperar(app, "Ejecucion")
        for _ in range(int(seg * 20)):
            if app.screen.terminado:
                return
            await asyncio.sleep(0.05)
        self.fail("la ejecución no terminó")

    async def esperar_que(self, condicion, seg: float = 5) -> bool:
        for _ in range(int(seg * 20)):
            if condicion():
                return True
            await asyncio.sleep(0.05)
        return False

    def en_papelera(self, nombre: str) -> bool:
        return (self.papelera / nombre).exists()


class TestNavegacion(BaseTUI):
    async def test_menu_informe_y_atras(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            await self.esperar(app, "MenuScreen")
            await pilot.press("alt+left")
            await self.esperar(app, "MenuScreen")  # en el menú, «atrás» no hace nada

            await pilot.press("a")
            await self.esperar(app, "Vista")
            await pilot.click("#limpiar")
            await self.esperar(app, "SeleccionScreen")
            await pilot.press("alt+left")
            await self.esperar(app, "Vista")       # desde la lista, «atrás» vuelve al informe
            await pilot.click("#volver")
            await self.esperar(app, "MenuScreen")

    async def test_actualizar_vuelve_a_analizar(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            await self.esperar(app, "MenuScreen")
            await pilot.press("a")
            await self.esperar(app, "Vista")
            antes = appmod.analizar.call_count
            await pilot.click("#actualizar")
            self.assertTrue(await self.esperar_que(lambda: appmod.analizar.call_count == antes + 1))
            await self.esperar(app, "Vista")
            await pilot.press("escape")
            await self.esperar(app, "MenuScreen")


class TestLimpiar(BaseTUI):
    async def _hasta_el_plan(self, app, pilot, tecla: str = "l"):
        await self.esperar(app, "MenuScreen")
        await pilot.press(tecla)
        await self.esperar(app, "SeleccionScreen")

    async def test_seguros_tildados_por_defecto_y_revisar_no(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            await self._hasta_el_plan(app, pilot)
            await pilot.click("#continuar")
            await self.esperar(app, "PlanScreen")
            await pilot.click("#ejecutar")
            await self.esperar_fin(app)
            await pilot.click("#menu")
            await self.esperar(app, "MenuScreen")
        self.assertFalse(self.cache.exists(), "la caché 🟢 tenía que borrarse")
        self.assertTrue(self.video.exists(), "lo 🟡 no viene tildado: no se tenía que tocar")
        self.assertTrue((self.home / ".local/state/archcleaner/acciones.log").exists(), "el log va al home falso")

    async def test_atras_desde_el_plan_conserva_la_seleccion(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            await self._hasta_el_plan(app, pilot)
            await pilot.click("#ninguno")
            await pilot.pause()
            sel = app.screen.marcados
            self.assertEqual(sel, set())
            app.screen.marcados = {"h2-0"}  # solo el video (ítem 0 del hallazgo #2)
            await pilot.click("#continuar")
            await self.esperar(app, "PlanScreen")
            await pilot.press("alt+left")
            await self.esperar(app, "SeleccionScreen")
            self.assertEqual(app.screen.marcados, {"h2-0"})
            await pilot.click("#cancelar")
            await self.esperar(app, "MenuScreen")
        self.assertTrue(self.cache.exists() and self.video.exists(), "se canceló: no se borra nada")

    async def _plan_con_video(self, app, pilot, destino: int):
        await self._hasta_el_plan(app, pilot)
        app.screen.marcados |= {"h2-0"}
        await pilot.click("#continuar")
        await self.esperar(app, "PlanScreen")
        await pilot.click(list(app.screen.query("RadioButton"))[destino])
        await pilot.click("#ejecutar")

    async def test_papelera_por_defecto(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            await self._plan_con_video(app, pilot, destino=0)
            await self.esperar_fin(app)
        self.assertFalse(self.video.exists())
        self.assertTrue(self.en_papelera("viejo.mkv"), "el video tenía que ir a la papelera (falsa)")

    async def test_definitivo_exige_escribir_borrar(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            await self._plan_con_video(app, pilot, destino=1)
            await self.esperar(app, "ConfirmarBorrado")
            si = app.screen.query_one("#si")
            self.assertTrue(si.disabled, "sin escribir nada, el botón tiene que estar apagado")
            for c in "borra":
                await pilot.press(c)
            self.assertTrue(si.disabled, "«borra» no alcanza")
            await pilot.press("r")
            self.assertFalse(si.disabled)
            await pilot.click("#si")
            await self.esperar_fin(app)
        self.assertFalse(self.video.exists())
        self.assertFalse(self.en_papelera("viejo.mkv"), "definitivo: no tenía que pasar por la papelera")

    async def test_si_no_se_confirma_el_definitivo_va_a_la_papelera(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            await self._plan_con_video(app, pilot, destino=1)
            await self.esperar(app, "ConfirmarBorrado")
            await pilot.click("#no")
            await self.esperar_fin(app)
        self.assertTrue(self.en_papelera("viejo.mkv"))

    async def test_simulacro_no_ejecuta_nada(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            await self._hasta_el_plan(app, pilot, tecla="s")
            await pilot.click("#continuar")
            await self.esperar(app, "PlanScreen")
            self.assertEqual(len(app.screen.query("#ejecutar")), 0, "en simulacro no hay botón de ejecutar")
            await pilot.click("#volver")
            await self.esperar(app, "MenuScreen")
        self.assertTrue(self.cache.exists() and self.video.exists())


class TestHistorial(BaseTUI):
    async def test_sin_historial_y_despues_con(self):
        from archcleaner import historial
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            await self.esperar(app, "MenuScreen")
            await pilot.press("c")
            await self.esperar(app, "Vista")            # todavía no hay con qué comparar
            await pilot.click("#volver")
            await self.esperar(app, "MenuScreen")
            # una foto "de hace 2 días" en la que el video no estaba
            vieja = historial.foto_de(self._resultado(), ahora=time.time() - 2 * 86400)
            vieja.carpetas.pop(str(self.video.parent), None)  # (pesa < 1 MB: ya no estaba)
            historial.guardar(vieja)
            _archivo(self.home / "Videos/nuevo.mkv", 60 * 1024)   # +60 MB
            await pilot.press("a")
            await self.esperar(app, "Vista")
            await pilot.click("#volver")
            await self.esperar(app, "MenuScreen")
            await pilot.press("c")
            await self.esperar(app, "CrecioScreen")
            from rich.console import Console
            consola = Console(width=110, record=True, file=io.StringIO())
            consola.print(app.screen.query_one("#contenido").content)
            texto = consola.export_text()
            self.assertIn("Videos", texto)
            self.assertIn("nueva", texto)
            await pilot.click("#volver")
            await self.esperar(app, "MenuScreen")
        self.assertEqual(len(list((self.home / ".local/state/archcleaner/historial").iterdir())), 2,
                         "el historial va al home falso")


class TestExplorar(BaseTUI):
    async def _abrir(self, app, pilot, ruta: Path):
        await self.esperar(app, "MenuScreen")
        app.iniciar("explorar", str(ruta))
        await self.esperar(app, "ExplorarScreen")
        return app.screen

    def _resaltar(self, ex, nombre: str) -> None:
        ex.query_one("OptionList").highlighted = next(i for i, e in enumerate(ex.entradas) if e.nombre == nombre)

    async def test_ordena_por_peso_entra_y_vuelve(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            ex = await self._abrir(app, pilot, self.home / "Juegos")
            self.assertEqual([e.nombre for e in ex.entradas], ["grande", "chico.txt"])
            await pilot.press("enter")                # entra a la más pesada
            self.assertEqual(ex.actual, str(self.home / "Juegos/grande"))
            await pilot.press("alt+left")
            self.assertEqual(ex.actual, str(self.home / "Juegos"))
            await pilot.press("alt+right")
            self.assertEqual(ex.actual, str(self.home / "Juegos/grande"))
            await pilot.click("#cerrar")
            await self.esperar(app, "MenuScreen")

    async def test_papelera_desde_explorar(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            ex = await self._abrir(app, pilot, self.home / "Juegos")
            self._resaltar(ex, "chico.txt")
            await pilot.click("#papelera")
            await self.esperar(app, "Dialogo")
            await pilot.click("#si")
            await self.esperar(app, "ExplorarScreen")
            self.assertTrue(await self.esperar_que(lambda: self.en_papelera("chico.txt")))
            self.assertEqual([e.nombre for e in ex.entradas], ["grande"])

    async def test_fuera_del_home_es_solo_lectura(self):
        app = ArchCleanerApp()
        async with app.run_test(size=TAMANO) as pilot:
            ex = await self._abrir(app, pilot, Path("/usr"))
            ex.query_one("OptionList").highlighted = 0
            await pilot.click("#borrar")
            await pilot.pause()
            await asyncio.sleep(0.2)
            self.assertEqual(type(app.screen).__name__, "ExplorarScreen", "no tenía que ofrecer borrar nada")

    async def test_elegir_disco_y_ruta_escrita(self):
        for ancho in (80, 110):
            with self.subTest(ancho=ancho):
                app = ArchCleanerApp()
                async with app.run_test(size=(ancho, 30)) as pilot:
                    await self.esperar(app, "MenuScreen")
                    await pilot.press("e")
                    await self.esperar(app, "ElegirRaiz")
                    await pilot.click("#ruta-manual")
                    for c in "~/Videos":
                        await pilot.press(c)
                    await pilot.press("enter")
                    await self.esperar(app, "ExplorarScreen")
                    self.assertEqual(app.screen.actual, str(self.home / "Videos"))


class TestDesinstalar(BaseTUI):
    async def test_appimage_de_punta_a_punta(self):
        app = ArchCleanerApp(inicio="desinstalar")
        async with app.run_test(size=TAMANO) as pilot:
            await self.esperar(app, "ElegirProgramaScreen")
            for c in "zzprueba":
                await pilot.press(c)
            await pilot.click("#elegir")
            await self.esperar(app, "Vista")
            await pilot.click("#seguir")
            await self.esperar(app, "SeleccionScreen")
            await pilot.press("alt+left")
            await self.esperar(app, "Vista")        # restos → atrás → ficha
            await pilot.click("#seguir")
            await self.esperar(app, "SeleccionScreen")
            await pilot.click("#continuar")
            await self.esperar(app, "PlanScreen")
            await pilot.click("#ejecutar")
            await self.esperar_fin(app)
        self.assertFalse(self.appimage.exists())
        self.assertTrue(self.en_papelera("Zzprueba.AppImage"))
        self.assertFalse((self.home / ".config/Zzprueba").exists(), "su configuración era un resto seguro")

    async def test_ordenar_y_recordar_el_orden(self):
        for _ in range(2):  # la segunda vez tiene que arrancar con el orden elegido la primera
            app = ArchCleanerApp(inicio="desinstalar")
            async with app.run_test(size=TAMANO) as pilot:
                await self.esperar(app, "ElegirProgramaScreen")
                if app.screen.orden == "tamano":
                    await pilot.press("f2")
                    self.assertEqual(app.screen.orden, "uso")
                else:
                    self.assertEqual(app.screen.orden, "uso")
                await pilot.press("escape")
                await self.esperar(app, "MenuScreen")

    async def test_cancelar_no_toca_nada(self):
        app = ArchCleanerApp(inicio="desinstalar", programa="zzprueba")
        async with app.run_test(size=TAMANO) as pilot:
            await self.esperar(app, "Vista")
            await pilot.click("#volver")
            await self.esperar(app, "MenuScreen")
        self.assertTrue(self.appimage.exists())


if __name__ == "__main__":
    unittest.main()
