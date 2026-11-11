"""🤖 "¿Qué es esto?": la IA local se prueba contra un Ollama FALSO (un servidor HTTP en localhost).

No hace falta tener Ollama instalado: se verifica qué se le manda al modelo, que la app no le crea
de más (ante la duda, "perdés datos"), los errores y que sin Ollama el botón ni aparece.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ARCHCLEANER_LANG"] = "es"

from test_tui import TAMANO, BaseTUI

from archcleaner import ia
from archcleaner.tui.app import ArchCleanerApp


class OllamaFalso(BaseHTTPRequestHandler):
    respuesta: ClassVar[dict] = {}
    modelos: ClassVar[list[str]] = ["qwen3.5:9b"]
    pedidos: ClassVar[list[dict]] = []

    def _json(self, codigo: int, cuerpo: dict) -> None:
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self) -> None:
        self._json(200, {"models": [{"name": m} for m in self.modelos]})

    def do_POST(self) -> None:
        cuerpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        OllamaFalso.pedidos.append(cuerpo)
        if cuerpo["model"] not in self.modelos:
            self._json(404, {"error": "model not found"})
        else:
            self._json(200, {"message": {"role": "assistant", "content": json.dumps(self.respuesta)}})

    def log_message(self, *args) -> None:
        pass


def _respuesta(known=True, what="Caché de pip.", program="pip", if_deleted="rebuilt", detail="Se vuelve a bajar.") -> dict:
    return {"known": known, "what": what, "program": program, "if_deleted": if_deleted, "detail": detail}


PIP = ia.Datos("~/.cache/pip", True, "2.3 GB", [], [("http-v2/", "2.1 GB"), ("wheels/", "180 MB")])


class ConOllama(unittest.TestCase):
    def setUp(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), OllamaFalso)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        p = mock.patch.dict(os.environ, {"OLLAMA_HOST": f"127.0.0.1:{self.server.server_port}",
                                         "ARCHCLEANER_MODELO": ""})
        p.start()
        self.addCleanup(p.stop)
        OllamaFalso.pedidos = []
        OllamaFalso.respuesta = _respuesta()


class TestPedido(ConOllama):
    def test_manda_ruta_peso_paquete_y_lo_de_adentro_en_json(self):
        self.assertTrue(ia.disponible())
        self.assertTrue(ia.tiene_modelo())
        r = ia.preguntar(PIP, "es")
        self.assertEqual((r.conocido, r.programa, r.efecto), (True, "pip", "rebuilt"))
        p = OllamaFalso.pedidos[0]
        self.assertEqual(p["model"], "qwen3.5:9b")
        self.assertIs(p["think"], False)
        self.assertEqual(p["format"], ia.ESQUEMA)
        usuario = p["messages"][1]["content"]
        for esperado in ("Path: ~/.cache/pip", "Size: 2.3 GB", "Owning package: none", "- http-v2/ (2.1 GB)",
                         "Answer in Spanish."):
            self.assertIn(esperado, usuario)
        self.assertIn("in Spanish (impersonal", p["messages"][0]["content"])

    def test_en_ingles(self):
        ia.preguntar(PIP, "en")
        p = OllamaFalso.pedidos[0]
        self.assertIn("Answer in English.", p["messages"][1]["content"])
        self.assertNotIn("impersonal", p["messages"][0]["content"])

    def test_modelo_configurable_y_si_falta_dice_como_bajarlo(self):
        with mock.patch.dict(os.environ, {"ARCHCLEANER_MODELO": "otro:3b"}):
            self.assertFalse(ia.tiene_modelo())
            with self.assertRaises(ia.SinIA) as e:
                ia.preguntar(PIP, "es")
        self.assertIn("ollama pull otro:3b", str(e.exception))

    def test_json_roto(self):
        with mock.patch.object(OllamaFalso, "respuesta", "no es un objeto"), self.assertRaises(ia.SinIA):
            ia.preguntar(PIP, "es")


class TestDelLadoSeguro(ConOllama):
    def test_si_no_lo_conoce_no_nombra_programas_ni_promete_que_se_regenera(self):
        OllamaFalso.respuesta = _respuesta(known=False, what="Archivos de datos con un índice.", program="Zentrova",
                                           if_deleted="rebuilt")
        d = ia.Datos("~/.qorvex", True, "900 MB")
        r = ia.preguntar(d, "es")
        self.assertEqual((r.programa, r.efecto, r.detalle), ("", "data", ""))  # el detalle era de "se regenera"
        texto = "\n".join(ia.lineas(r, d))
        self.assertIn("No estoy seguro de qué es.", texto)
        self.assertIn("Si se borra, perdés datos.", texto)
        self.assertNotIn("Zentrova", texto)

    def test_efecto_desconocido_es_datos(self):
        OllamaFalso.respuesta = _respuesta(if_deleted="nada")
        self.assertEqual(ia.preguntar(PIP, "es").efecto, "data")

    def test_mayuscula_inicial(self):
        OllamaFalso.respuesta = _respuesta(what="caché de pip.", detail="se vuelve a bajar.")
        r = ia.preguntar(PIP, "es")
        self.assertEqual((r.que, r.detalle), ("Caché de pip.", "Se vuelve a bajar."))

    def test_paquete_solo_si_pacman_lo_confirma(self):
        OllamaFalso.respuesta = _respuesta(if_deleted="package")
        self.assertEqual(ia.preguntar(PIP, "es").efecto, "data")
        con_paquete = ia.Datos("/opt/kalvium-studio", True, "1.8 GB", ["kalvium-studio-bin 4.2.1-1"])
        OllamaFalso.respuesta = _respuesta(known=False, program="", if_deleted="package", detail="")
        r = ia.preguntar(con_paquete, "es")
        self.assertEqual(r.efecto, "package")
        self.assertIn("Lo instaló el paquete kalvium-studio-bin.", ia.lineas(r, con_paquete))

    def test_carpeta_de_varios_paquetes(self):
        d = ia.Datos("/usr/share/fonts", True, "1 GB", [f"fuente{i} 1.0-1" for i in range(7)])
        self.assertIn("Owning package: fuente0 1.0-1, fuente1 1.0-1, fuente2 1.0-1, fuente3 1.0-1, fuente4 1.0-1, …",
                      ia.mensaje(d, "es"))
        r = ia.Respuesta(False, "Fuentes.", "", "package", "")
        self.assertIn("Lo instalaron 7 paquetes: fuente0, fuente1, fuente2, fuente3, fuente4, ….", ia.lineas(r, d))

    def test_lineas_si_lo_conoce(self):
        r = ia.preguntar(PIP, "es")
        self.assertEqual(ia.lineas(r, PIP), ["Caché de pip.", "Lo usa: pip.", "Si se borra, se regenera solo. Se vuelve a bajar."])


class TestSinOllama(unittest.TestCase):
    def test_no_disponible(self):
        with mock.patch.dict(os.environ, {"OLLAMA_HOST": "127.0.0.1:9"}):  # puerto 9: nadie escucha
            self.assertFalse(ia.disponible())
            with self.assertRaises(ia.SinIA):
                ia.preguntar(PIP, "es")


class TestPantalla(BaseTUI):
    async def _explorar(self, app: ArchCleanerApp, pilot) -> None:
        app.flujo_explorar(str(self.home))
        await self.esperar(app, "ExplorarScreen")
        await pilot.pause()

    async def test_sin_ollama_no_hay_boton(self):
        app = ArchCleanerApp()
        with mock.patch.object(ia, "disponible", return_value=False):
            async with app.run_test(size=TAMANO) as pilot:
                await self._explorar(app, pilot)
                self.assertFalse(app.screen.query_one("#que_es").display)
                await pilot.press("question_mark")
                await pilot.pause()
                self.assertEqual(type(app.screen).__name__, "ExplorarScreen")

    async def test_con_ollama_explica_y_avisa_que_puede_equivocarse(self):
        app = ArchCleanerApp()
        r = ia.Respuesta(True, "Carpeta de juegos de prueba.", "Ninguno", "data", "Se pierden los juegos.")
        with mock.patch.object(ia, "disponible", return_value=True), \
                mock.patch.object(ia, "preguntar", return_value=r) as preguntar:
            async with app.run_test(size=TAMANO) as pilot:
                await self._explorar(app, pilot)
                self.assertTrue(await self.esperar_que(lambda: app.screen.query_one("#que_es").display))
                await pilot.press("question_mark")
                await self.esperar(app, "QueEsEsto")
                self.assertTrue(await self.esperar_que(lambda: not app.screen.query_one("#pensando").display))
                texto = str(app.screen.query_one("#respuesta").render())
                self.assertIn("Si se borra, perdés datos. Se pierden los juegos.", texto)
                datos = preguntar.call_args.args[0]
                self.assertTrue(datos.ruta.startswith("~/"))
                self.assertFalse(app.screen.query("#borrar") or app.screen.query("#papelera"))  # acá no se borra
                await pilot.press("escape")
                await self.esperar(app, "ExplorarScreen")


if __name__ == "__main__":
    unittest.main()
