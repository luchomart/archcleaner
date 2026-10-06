"""Tests de lo que borra: seguridad + acciones, siempre sobre carpetas temporales falsas.

Correr con:  python -m unittest discover -s tests
"""

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ARCHCLEANER_LANG"] = "es"  # los tests verifican los textos en español

from archcleaner import acciones
from archcleaner.acciones import armar_tarea, ejecutar
from archcleaner.modelo import Hallazgo, Item, Limpieza, Modo, Nivel
from archcleaner.seguridad import Verificador


def hallazgo(modo, rutas=(), detalle=(), **kw):
    return Hallazgo("Test", "prueba", Nivel.SEGURO, 0, "", rutas=list(rutas), detalle=list(detalle),
                    limpieza=Limpieza(modo, **kw))


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        (self.home / ".cache/app").mkdir(parents=True)
        (self.home / ".cache/app/a.bin").write_bytes(b"x" * 100)
        (self.home / "Documentos").mkdir()
        (self.home / "Documentos/importante.txt").write_text("no tocar")
        self.verif = Verificador(home=self.home)
        self.verif.personales |= {str(self.home / "Documentos")}
        log = mock.patch.object(acciones, "LOG", Path(self._tmp.name) / "acciones.log")
        log.start()
        self.addCleanup(log.stop)

    def tearDown(self):
        self._tmp.cleanup()


class TestSeguridad(Base):
    def test_rutas_del_sistema_bloqueadas(self):
        for r in ("/", "/usr", "/etc", "/home", "/boot", "/usr/bin/ls", "/etc/fstab", "/var/log"):
            self.assertIsNotNone(self.verif.problema(r), r)

    def test_home_y_personales_bloqueados(self):
        self.assertIsNotNone(self.verif.problema(self.home))
        self.assertIsNotNone(self.verif.problema(self.home / ".cache"))
        self.assertIsNotNone(self.verif.problema(self.home / "Documentos"))

    def test_vaciar_solo_cache_y_papelera(self):
        self.assertIsNone(self.verif.problema(self.home / ".cache", vaciar=True))
        self.assertIsNotNone(self.verif.problema(self.home, vaciar=True))
        self.assertIsNotNone(self.verif.problema(self.home / "Documentos", vaciar=True))

    def test_adentro_del_home_permitido(self):
        self.assertIsNone(self.verif.problema(self.home / ".cache/app"))

    def test_kernel_actual_protegido(self):
        actual = f"/usr/lib/modules/{os.uname().release}"
        if os.path.exists(actual):
            self.assertIsNotNone(self.verif.problema(actual))

    def test_restos_de_sistema_vitales_bloqueados(self):
        for r in ("/etc/fstab", "/etc/hostname", "/etc/machine-id", "/etc/pacman.conf", "/var/lib/pacman",
                  "/var/lib", "/etc", "/etc/systemd/system"):
            if os.path.exists(r):
                self.assertIsNotNone(self.verif.problema(r), r)

    def test_resto_de_sistema_solo_si_nadie_lo_reconoce(self):
        with mock.patch("os.path.exists", return_value=True), \
                mock.patch("pathlib.Path.exists", return_value=True), \
                mock.patch("subprocess.run") as run:
            run.return_value.returncode = 1  # pacman -Qo: ningún paquete lo tiene
            self.assertIsNone(self.verif.problema("/var/lib/programa-borrado"))
            run.return_value.returncode = 0  # es de un paquete
            self.assertIsNotNone(self.verif.problema("/var/lib/programa-borrado"))
            # más profundo que un nivel: nunca
            self.assertIsNotNone(self.verif.problema("/var/lib/algo/adentro"))

    def test_datos_y_codigo_de_archcleaner_protegidos(self):
        estado = self.home / ".local/state/archcleaner"
        estado.mkdir(parents=True)
        self.assertIsNotNone(self.verif.problema(estado))
        codigo = Path(__file__).resolve().parent.parent / "archcleaner"
        self.assertIsNotNone(self.verif.problema(codigo))

    def test_enlace_en_el_camino_no_engana(self):
        # ~/enlace -> /usr: «~/enlace/bin» parece estar en el home, pero es /usr/bin
        (self.home / "enlace").symlink_to("/usr")
        motivo = self.verif.problema(self.home / "enlace/bin")
        self.assertIsNotNone(motivo)
        self.assertIn("enlace", motivo)
        # un enlace que apunta adentro del home sigue estando permitido
        (self.home / "atajo").symlink_to(self.home / ".cache")
        self.assertIsNone(self.verif.problema(self.home / "atajo/app"))

    def test_carpeta_huerfana_con_archivos_de_paquetes_bloqueada(self):
        from archcleaner import seguridad
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "x.conf").write_text("")
            salida = mock.Mock(stdout=f"{d}/x.conf is owned by algo 1.0\n", returncode=0)
            with mock.patch.object(seguridad.subprocess, "run", return_value=salida):
                self.assertEqual(seguridad._archivo_de_paquete_adentro(Path(d)), f"{d}/x.conf")
            salida = mock.Mock(stdout="", returncode=1)
            with mock.patch.object(seguridad.subprocess, "run", return_value=salida):
                self.assertIsNone(seguridad._archivo_de_paquete_adentro(Path(d)))

    def test_inexistente(self):
        self.assertEqual(self.verif.problema(self.home / "nada"), "ya no existe")


class TestAcciones(Base):
    def test_borrar_por_item_solo_lo_elegido(self):
        (self.home / ".cache/otra").mkdir()
        h = hallazgo(Modo.BORRAR, detalle=[Item("app", 100, self.home / ".cache/app"),
                                           Item("otra", 0, self.home / ".cache/otra")], por_item=True)
        r = ejecutar(armar_tarea(h, [0]), self.verif, salida=lambda s: None)
        self.assertTrue(r.ok, r.errores)
        self.assertFalse((self.home / ".cache/app").exists())
        self.assertTrue((self.home / ".cache/otra").exists())

    def test_borrar_cache_de_solo_lectura(self):
        d = self.home / ".cache/go-mod/pkg"
        d.mkdir(parents=True)
        (d / "f.go").write_text("x")
        os.chmod(d / "f.go", stat.S_IRUSR)
        os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)
        h = hallazgo(Modo.BORRAR, rutas=[self.home / ".cache/go-mod"])
        r = ejecutar(armar_tarea(h), self.verif, salida=lambda s: None)
        self.assertTrue(r.ok, r.errores)
        self.assertFalse((self.home / ".cache/go-mod").exists())

    def test_arreglo_de_permisos_no_sale_de_lo_que_se_borra(self):
        # la carpeta madre es de solo lectura: no se le tienen que cambiar los permisos para borrar adentro
        madre = self.home / "solo-lectura"
        (madre / "hija").mkdir(parents=True)
        madre.chmod(0o555)
        try:
            t = armar_tarea(hallazgo(Modo.BORRAR, rutas=[madre / "hija"]))
            r = ejecutar(t, self.verif, salida=lambda _: None)
            self.assertFalse(r.ok)
            self.assertEqual(stat.S_IMODE(madre.stat().st_mode), 0o555, "no se tocaron los permisos de la madre")
            self.assertTrue((madre / "hija").exists())
        finally:
            madre.chmod(0o755)

    def test_vaciar_deja_la_carpeta(self):
        h = hallazgo(Modo.VACIAR, rutas=[self.home / ".cache"])
        r = ejecutar(armar_tarea(h), self.verif, salida=lambda s: None)
        self.assertTrue(r.ok, r.errores)
        self.assertTrue((self.home / ".cache").is_dir())
        self.assertEqual(list((self.home / ".cache").iterdir()), [])

    def test_nunca_borra_protegidas_aunque_un_detector_las_pida(self):
        h = hallazgo(Modo.BORRAR, rutas=[self.home / "Documentos", self.home])
        r = ejecutar(armar_tarea(h), self.verif, salida=lambda s: None)
        self.assertFalse(r.ok)
        self.assertTrue((self.home / "Documentos/importante.txt").exists())

    def test_vaciar_home_bloqueado(self):
        h = hallazgo(Modo.VACIAR, rutas=[self.home])
        r = ejecutar(armar_tarea(h), self.verif, salida=lambda s: None)
        self.assertFalse(r.ok)
        self.assertTrue((self.home / "Documentos/importante.txt").exists())

    def test_symlink_borra_el_enlace_no_el_destino(self):
        enlace = self.home / ".cache/enlace"
        enlace.symlink_to(self.home / "Documentos")
        h = hallazgo(Modo.BORRAR, rutas=[enlace])
        r = ejecutar(armar_tarea(h), self.verif, salida=lambda s: None)
        self.assertTrue(r.ok, r.errores)
        self.assertFalse(enlace.is_symlink())
        self.assertTrue((self.home / "Documentos/importante.txt").exists())

    def test_rm_de_comando_verificado(self):
        h = hallazgo(Modo.COMANDO, comandos=[["rm", "-rf", "--", "/etc"]])
        with mock.patch("subprocess.run") as run:
            r = ejecutar(armar_tarea(h), self.verif, salida=lambda s: None)
        self.assertFalse(r.ok)
        self.assertIn("bloqueado", r.mensaje)
        run.assert_not_called()

    def test_proceso_abierto_saltea(self):
        h = hallazgo(Modo.BORRAR, rutas=[self.home / ".cache/app"], cerrar=["steam"])
        with mock.patch.object(acciones, "procesos_abiertos", return_value=["steam"]):
            r = ejecutar(armar_tarea(h), self.verif, salida=lambda s: None)
        self.assertFalse(r.ok)
        self.assertTrue((self.home / ".cache/app").exists())

    def test_definitivo_borra_en_vez_de_papelera(self):
        h = hallazgo(Modo.PAPELERA, detalle=[Item("app", 100, self.home / ".cache/app")], por_item=True)
        tarea = armar_tarea(h, [0])
        tarea.definitivo = True
        with mock.patch.object(acciones, "_a_papelera") as papelera:
            r = ejecutar(tarea, self.verif, salida=lambda s: None)
        self.assertTrue(r.ok, r.errores)
        papelera.assert_not_called()
        self.assertFalse((self.home / ".cache/app").exists())

    def test_definitivo_igual_respeta_seguridad(self):
        h = hallazgo(Modo.PAPELERA, detalle=[Item("docs", 0, self.home / "Documentos")], por_item=True)
        tarea = armar_tarea(h, [0])
        tarea.definitivo = True
        r = ejecutar(tarea, self.verif, salida=lambda s: None)
        self.assertFalse(r.ok)
        self.assertTrue((self.home / "Documentos/importante.txt").exists())

    def test_lo_que_ya_no_existe_no_es_error(self):
        h = hallazgo(Modo.BORRAR, detalle=[Item("app", 100, self.home / ".cache/app"),
                                           Item("borrada", 0, self.home / ".cache/borrada-a-mano")], por_item=True)
        r = ejecutar(armar_tarea(h, [0, 1]), self.verif, salida=lambda s: None)
        self.assertTrue(r.ok, r.errores)
        self.assertIn("1 ya no estaban", r.mensaje)

    def test_rm_saca_las_rutas_que_ya_no_existen(self):
        existe = self.home / ".cache/app"
        h = hallazgo(Modo.COMANDO, comandos=[["rm", "-r", "--", str(existe), str(self.home / "no-existe")]])
        llamados = []
        r = ejecutar(armar_tarea(h), self.verif, salida=lambda s: None,
                     correr=lambda cmd: llamados.append(cmd) or 0)
        self.assertTrue(r.ok)
        self.assertEqual(llamados, [["rm", "-r", "--", str(existe)]])

    def test_rm_de_algo_que_ya_no_existe_no_corre(self):
        h = hallazgo(Modo.COMANDO, comandos=[["rm", "-r", "--", str(self.home / "no-existe")]])
        llamados = []
        r = ejecutar(armar_tarea(h), self.verif, salida=lambda s: None, correr=lambda cmd: llamados.append(cmd) or 0)
        self.assertTrue(r.ok)
        self.assertEqual(llamados, [])

    def test_queda_en_el_log(self):
        h = hallazgo(Modo.BORRAR, rutas=[self.home / ".cache/app"])
        ejecutar(armar_tarea(h), self.verif, salida=lambda s: None)
        self.assertIn("prueba", acciones.LOG.read_text())


if __name__ == "__main__":
    unittest.main()


class TestDetectoresHome(unittest.TestCase):
    """Lo que se ofrece tildado por defecto (🟢) tiene que ser de verdad sin riesgo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        for rel in (".cache/thumbnails/a", ".cache/huggingface/modelo", ".local/share/Trash/files/viejo"):
            (self.home / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.home / rel).write_bytes(b"x" * (11 * 1024**2))

    def test_papelera_y_caches_caras_no_vienen_tildadas(self):
        from archcleaner.contexto import Contexto
        from archcleaner.detectores import home
        ctx = Contexto(home=self.home)
        with mock.patch.object(home, "ejecutar", return_value=""):
            hallazgos = home._cache(ctx) + home._papeleras(ctx)
        nivel = {h.titulo: h.nivel for h in hallazgos}
        self.assertEqual(nivel["Papelera"], Nivel.REVISAR)
        self.assertEqual(nivel["Cachés que cuesta regenerar (~/.cache)"], Nivel.REVISAR)
        self.assertEqual(nivel["Caché de programas (~/.cache)"], Nivel.SEGURO)
        seguros = [i.nombre for h in hallazgos if h.nivel == Nivel.SEGURO for i in h.detalle]
        self.assertEqual(seguros, ["thumbnails"])
