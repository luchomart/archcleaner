"""Genera las capturas del README con una PC de demostración: docs/capturas/*.svg (español) y
docs/capturas/en/*.svg (inglés).

Nada sale de tu PC: el home, los discos, los programas y el historial son inventados, y no se
borra ni se instala nada (no se aprieta ningún botón que ejecute).

    python docs/generar_capturas.py            # las dos
    python docs/generar_capturas.py --lang en  # solo una
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import time
from collections import namedtuple
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

if "--lang" not in sys.argv:  # cada idioma en su propio proceso: los textos se arman al importar
    import subprocess
    for idioma in ("es", "en"):
        subprocess.run([sys.executable, __file__, "--lang", idioma], check=True)
    sys.exit(0)
IDIOMA = sys.argv[sys.argv.index("--lang") + 1]
os.environ["ARCHCLEANER_LANG"] = IDIOMA

from archcleaner import estado, historial  # noqa: E402
from archcleaner.i18n import tr  # noqa: E402
from archcleaner.analisis import Resultado  # noqa: E402
from archcleaner.contexto import Contexto  # noqa: E402
from archcleaner.escaner import ResultadoEscaneo  # noqa: E402
from archcleaner.modelo import Hallazgo, Item, Limpieza, Modo, Nivel  # noqa: E402
from archcleaner.programas import Programa  # noqa: E402
from archcleaner.tui import app as appmod  # noqa: E402
from archcleaner.tui import menu  # noqa: E402
from archcleaner.tui.app import ArchCleanerApp  # noqa: E402

SALIDA = RAIZ / "docs/capturas" / ("" if IDIOMA == "es" else IDIOMA)
TAMANO = (112, 36)
GB, MB = 1024**3, 1024**2
DIA = 86400
Uso = namedtuple("Uso", "total used free")
# nombres de las carpetas personales de la PC de demostración, en el idioma de la captura
C = ({"Juegos": "Juegos", "Descargas": "Descargas", "Proyectos": "Proyectos", "Documentos": "Documentos",
      "Imágenes": "Imágenes", "Aplicaciones": "Aplicaciones"} if IDIOMA == "es" else
     {"Juegos": "Games", "Descargas": "Downloads", "Proyectos": "Projects", "Documentos": "Documents",
      "Imágenes": "Pictures", "Aplicaciones": "Applications"})


def disco(_ruta) -> Uso:
    return Uso(500 * GB, 342 * GB, 158 * GB)


class Demo:
    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="archcleaner-demo-"))
        self.home = self.tmp / "home/usuario"
        h = self.home
        for rel in (".cache/mesa_shader_cache", ".cache/google-chrome", ".cache/thumbnails", ".cache/pip",
                    ".local/share/Steam/steamapps/common", ".local/share/Steam/steamapps/workshop",
                    ".config", f"{C['Descargas']}/isos", f"{C['Juegos']}/Hollow Knight", "Videos/2025",
                    f"{C['Proyectos']}/web/node_modules",
                    C["Documentos"], C["Imágenes"]):
            (h / rel).mkdir(parents=True, exist_ok=True)
        (h / f"{C['Descargas']}/ubuntu-24.04-desktop-amd64.iso").write_bytes(b"x" * 4096)
        (h / "Videos/2025/vacaciones.mp4").write_bytes(b"x" * 4096)
        self.estado = self.tmp / "estado"

    def escaneo(self) -> ResultadoEscaneo:
        h = str(self.home)
        total = {
            h: 182 * GB, f"{h}/.local": 96 * GB, f"{h}/.local/share": 95 * GB, f"{h}/.local/share/Steam": 88 * GB,
            f"{h}/.local/share/Steam/steamapps": 87 * GB, f"{h}/.local/share/Steam/steamapps/common": 79 * GB,
            f"{h}/.local/share/Steam/steamapps/workshop": 6 * GB, f"{h}/{C['Juegos']}": 38 * GB,
            f"{h}/{C['Juegos']}/Hollow Knight": 38 * GB, f"{h}/Videos": 21 * GB, f"{h}/Videos/2025": 21 * GB,
            f"{h}/{C['Descargas']}": 9 * GB, f"{h}/{C['Descargas']}/isos": 3 * GB, f"{h}/.cache": 4 * GB,
            f"{h}/.cache/mesa_shader_cache": 1600 * MB, f"{h}/.cache/google-chrome": 1200 * MB,
            f"{h}/.cache/thumbnails": 700 * MB, f"{h}/.cache/pip": 500 * MB, f"{h}/{C['Proyectos']}": 2 * GB,
            f"{h}/{C['Proyectos']}/web": 2 * GB, f"{h}/{C['Proyectos']}/web/node_modules": 1800 * MB, f"{h}/.config": 3 * GB,
            f"{h}/{C['Documentos']}": 2 * GB, f"{h}/{C['Imágenes']}": 6 * GB,
        }
        return ResultadoEscaneo(raiz=h, total=total)

    def resultado(self) -> Resultado:
        """Hallazgos como los de los detectores reales (con sus mismos textos, así se traducen)."""
        ctx = Contexto(home=self.home)
        ctx.escaneos = [self.escaneo()]
        h = self.home
        steam = "~/.local/share/Steam"
        H = [
            Hallazgo(tr("Pacman"), tr("Versiones viejas en la caché de paquetes"), Nivel.SEGURO, 3400 * MB,
                     tr("Pacman guarda cada versión que descargó (la caché pesa {total} en total). "
                        "Se conservan las 2 últimas de cada paquete por si una actualización sale mal y "
                        "necesitás volver atrás; se borran {n} versiones más viejas.", total="5.1 GB", n=143),
                     rutas=[Path("/var/cache/pacman/pkg")],
                     limpieza=Limpieza(Modo.COMANDO, [["paccache", "-rk2"]], sudo=True)),
            Hallazgo(tr("Home"), tr("Caché de programas (~/.cache)"), Nivel.SEGURO, 4000 * MB,
                     tr("Archivos temporales que los programas regeneran solos (miniaturas, caché del navegador, "
                        "etc.). Conviene cerrar los programas antes de limpiar. Lo único que notás es que la "
                        "primera vez algunas cosas cargan un poco más lento."),
                     rutas=[h / ".cache"], detalle=[
                         Item("mesa_shader_cache", 1600 * MB, h / ".cache/mesa_shader_cache"),
                         Item("google-chrome", 1200 * MB, h / ".cache/google-chrome"),
                         Item("thumbnails", 700 * MB, h / ".cache/thumbnails"),
                         Item("pip", 500 * MB, h / ".cache/pip")],
                     limpieza=Limpieza(Modo.BORRAR, por_item=True)),
            Hallazgo(tr("Sistema"), tr("Logs viejos del sistema (journald)"), Nivel.SEGURO, 1100 * MB,
                     tr("Los registros del sistema ocupan {usado}. Se recortan a los {objetivo} más recientes: "
                        "alcanza de sobra para diagnosticar problemas.", usado="1.3 GB", objetivo="200.0 MB"),
                     rutas=[Path("/var/log/journal")],
                     limpieza=Limpieza(Modo.COMANDO, [["journalctl", "--vacuum-size=200M"]], sudo=True)),
            Hallazgo(tr("Pacman"), tr("Paquetes huérfanos"), Nivel.SEGURO, 640 * MB,
                     tr("Se instalaron como dependencia de algo que ya desinstalaste y nadie más los usa. "
                        "Ojo: si alguno lo usás vos directamente (por ejemplo un compilador), quedátelo."),
                     detalle=[Item("python-sphinx", 210 * MB), Item("rust", 400 * MB), Item("go-tools", 30 * MB)],
                     limpieza=Limpieza(Modo.COMANDO, [["pacman", "-Rns", "python-sphinx", "rust", "go-tools"]],
                                       sudo=True)),
            Hallazgo(tr("Archivos"), tr("Juegos instalados por fuera de Steam"), Nivel.REVISAR, 38 * GB,
                     tr("No es basura: son juegos instalados a mano (Hydra, repacks, GOG...). Se muestran porque "
                        "pesan mucho: si ya no jugás alguno, borrar su carpeta libera todo eso. Ojo: con "
                        "Proton/Wine las partidas suelen guardarse en el prefijo, no acá, así que borrar el juego "
                        "no las borra."), rutas=[h / f"{C['Juegos']}/Hollow Knight"],
                     detalle=[Item(f"Hollow Knight  (~/{C['Juegos']})", 38 * GB, h / f"{C['Juegos']}/Hollow Knight")],
                     limpieza=Limpieza(Modo.PAPELERA, por_item=True)),
            Hallazgo(tr("Sistema"), tr("Snapshots de Timeshift de más de {n} días", n=30), Nivel.REVISAR, 12 * GB,
                     tr("Las snapshots manuales Timeshift no las borra nunca solo, así que se acumulan. "
                        "El peso es lo que se libera de verdad: solo los archivos que no comparte con otras "
                        "snapshots. La más reciente ({nombre}) se conserva siempre.", nombre="2026-10-01_09-00-00"),
                     detalle=[Item(tr("{nombre}  ({tipo}, hace {dias} días{nota})", nombre="2026-06-02_10-00-01",
                                      tipo=tr("manual"), dias=126, nota=""), 7 * GB, comando=["true"]),
                              Item(tr("{nombre}  ({tipo}, hace {dias} días{nota})", nombre="2026-08-14_18-30-00",
                                      tipo=tr("manual"), dias=53, nota=""), 5 * GB, comando=["true"])],
                     limpieza=Limpieza(Modo.COMANDO, sudo=True, por_item=True)),
            Hallazgo(tr("Steam"), tr("Workshop de {juego}", juego="Wallpaper Engine"), Nivel.REVISAR, 6 * GB,
                     tr("Contenido de Workshop al que estás suscripto ({n} ítems). Si lo borrás a mano, "
                        "Steam lo vuelve a bajar: la forma correcta es desuscribirte en Steam de lo que no uses. "
                        "Entre paréntesis va el ID: steamcommunity.com/sharedfiles/filedetails/?id=ID te lleva a "
                        "su página.", n=3),
                     rutas=[h / ".local/share/Steam/steamapps/workshop"], suma=False, detalle=[
                         Item("Neon City Rain 4K  (2891734455)", 2100 * MB), Item("Lofi Room  (1981236612)", 900 * MB),
                         Item("Aurora Borealis  (2311898720)", 640 * MB)]),
            Hallazgo(tr("Home"), tr("Descargas de hace más de {n} días", n=90), Nivel.REVISAR, 3 * GB,
                     tr("Instaladores, ISOs, comprimidos... cosas que bajaste hace rato y probablemente ya usaste."),
                     rutas=[h / f"{C['Descargas']}/ubuntu-24.04-desktop-amd64.iso"],
                     detalle=[Item("ubuntu-24.04-desktop-amd64.iso", 3 * GB,
                                   h / f"{C['Descargas']}/ubuntu-24.04-desktop-amd64.iso")],
                     limpieza=Limpieza(Modo.PAPELERA, por_item=True)),
            Hallazgo(tr("Desarrollo"), tr("Dependencias de proyectos (node_modules / venv)"), Nivel.REVISAR,
                     1800 * MB,
                     tr("Librerías instaladas por proyecto. Se regeneran con `npm install` o `pip install -r ...`. "
                        "Las de proyectos que no tocás hace rato son buenas candidatas."),
                     rutas=[h / f"{C['Proyectos']}/web/node_modules"],
                     detalle=[Item(f"~/{C['Proyectos']}/web/node_modules  (" + tr("sin tocar hace {n} días", n=140) + ")",
                                   1800 * MB, h / f"{C['Proyectos']}/web/node_modules")],
                     limpieza=Limpieza(Modo.PAPELERA, por_item=True)),
            Hallazgo(tr("Steam"), tr("Juegos instalados en {lib}", lib=steam), Nivel.INFO, 79 * GB,
                     tr("Lo que pesa cada juego (y herramientas como Proton). Si alguno no lo jugás más, "
                        "desinstalalo desde Steam."),
                     detalle=[Item("Cyberpunk 2077", 65 * GB), Item("Hades II", 9 * GB), Item("Terraria", 5 * GB)],
                     suma=False),
        ]
        for i, x in enumerate(H, 1):
            x.numero = i
        ctx.etiquetas[str(h / ".local/share/Steam/steamapps/common")] = tr("juego: {nombre}", nombre="Steam")
        return Resultado(ctx, H)

    def programas(self) -> list[Programa]:
        ahora = time.time()

        def p(id_, nombre, origen, gb, desc, uso_dias, inst_dias=200, conocido=True):
            return Programa(id_, nombre, origen, int(gb * GB), desc,
                            ultimo_uso=ahora - uso_dias * DIA if uso_dias is not None else None,
                            instalado=ahora - inst_dias * DIA, uso_conocido=conocido)

        def juego(appid):
            return tr("juego · appid {appid} · {donde}", appid=appid, donde="~/.local/share/Steam")
        return [
            p("1091500", "Cyberpunk 2077", "steam", 65, juego("1091500"), 210),
            p("1145350", "Hades II", "steam", 9, juego("1145350"), 2),
            p("android-studio", "android-studio", "aur", 2.9, "The official Android IDE", None, 300),
            p("libreoffice-fresh", "libreoffice-fresh", "repo", 1.4, "LibreOffice branch with new features", 45),
            p("com.spotify.Client", "Spotify", "flatpak", 0.9, "com.spotify.Client", 0),
            p("blender", "blender", "repo", 0.8, "A fully integrated 3D graphics creation suite", 380, 400),
            p("gimp", "gimp", "repo", 0.4, "GNU Image Manipulation Program", 12),
            p("obs-studio", "obs-studio", "repo", 0.2, "Free and open source software for video recording", 30),
            p(f"/home/usuario/{C['Aplicaciones']}/Krita.AppImage", "Krita", "appimage", 0.3,
              f"~/{C['Aplicaciones']}/Krita.AppImage",
              None, 90),
            p("htop", "htop", "repo", 0.001, "Interactive process viewer", 1),
        ]

    def historial(self) -> None:
        """Dos semanas de análisis: hace una semana no estaban los juegos y el Workshop era más chico."""
        h = str(self.home)
        base = self.escaneo().total
        for dias in range(14, 0, -1):
            antes = dias >= 7
            cambios = {f"{h}/.cache": (1200 + (14 - dias) * 200) * MB}
            if antes:
                cambios |= {f"{h}/{C['Juegos']}": 0, f"{h}/{C['Juegos']}/Hollow Knight": 0,
                            f"{h}/Videos": 22 * GB, f"{h}/Videos/2025": 22 * GB}
                for d in (".local", ".local/share", ".local/share/Steam", ".local/share/Steam/steamapps",
                          ".local/share/Steam/steamapps/workshop"):
                    cambios[f"{h}/{d}"] = base[f"{h}/{d}"] - 5 * GB
            carpetas = {k: v for k, v in {**base, **cambios}.items() if v}
            carpetas[h] = sum(v for k, v in carpetas.items() if k.count("/") == h.count("/") + 1)
            libre = 158 * GB + (base[h] - carpetas[h])
            historial.guardar(historial.Foto(time.time() - dias * DIA, [h], carpetas, {"/": [500 * GB, libre]},
                                             8 * GB, 50 * GB))


async def capturar(demo: Demo) -> None:
    res = demo.resultado()

    async def esperar(app, tipo):
        for _ in range(300):
            if type(app.screen).__name__ == tipo:
                await asyncio.sleep(0.2)
                return
            await asyncio.sleep(0.05)
        raise SystemExit(f"esperaba {tipo}, estoy en {type(app.screen).__name__}")

    def foto(app, nombre):
        app.save_screenshot(str(SALIDA / f"{nombre}.svg"))
        print("  ✔", nombre)

    app = ArchCleanerApp()
    async with app.run_test(size=TAMANO) as pilot:
        await esperar(app, "MenuScreen")
        foto(app, "menu")

        await pilot.press("a")
        await esperar(app, "Vista")
        foto(app, "analisis")
        await pilot.click("#limpiar")
        await esperar(app, "SeleccionScreen")
        foto(app, "limpiar")
        app.screen.marcados |= {"h5-0"}
        await pilot.click("#continuar")
        await esperar(app, "PlanScreen")
        await pilot.click(list(app.screen.query("RadioButton"))[1])
        await pilot.click("#ejecutar")
        await esperar(app, "ConfirmarBorrado")
        foto(app, "confirmar-borrado")
        await pilot.press("escape")          # «Mejor a la papelera»... no: escape cancela el modal
        await asyncio.sleep(0.3)
        app.exit()

    app = ArchCleanerApp(inicio="desinstalar")
    async with app.run_test(size=TAMANO) as pilot:
        await esperar(app, "ElegirProgramaScreen")
        app.screen.action_ordenar("uso")
        await asyncio.sleep(0.2)
        foto(app, "desinstalar")
        app.exit()

    app = ArchCleanerApp()
    app.resultado = res
    app.foto_anterior = historial.anterior(historial.ultima().fecha, 7)
    async with app.run_test(size=TAMANO) as pilot:
        await esperar(app, "MenuScreen")
        await pilot.press("c")
        await esperar(app, "CrecioScreen")
        app.screen.action_comparar("semana")
        await asyncio.sleep(0.2)
        foto(app, "que-crecio")
        await pilot.click("#volver")
        await esperar(app, "MenuScreen")
        app.iniciar("explorar", str(demo.home))
        await esperar(app, "ExplorarScreen")
        foto(app, "explorar")
        app.exit()


def main() -> None:
    demo = Demo()
    SALIDA.mkdir(parents=True, exist_ok=True)
    parches = [
        mock.patch.dict(os.environ, {"HOME": str(demo.home), "XDG_DATA_HOME": str(demo.home / ".local/share")}),
        mock.patch.object(estado, "ARCHIVO", demo.estado / "estado.json"),
        mock.patch.object(appmod, "analizar", side_effect=lambda *a, **k: demo.resultado()),
        mock.patch.object(appmod, "listar", side_effect=lambda *a, **k: demo.programas()),
        mock.patch.object(appmod, "guardar_analisis"),
        mock.patch.object(appmod, "guardar_tiempos"),
        mock.patch("shutil.disk_usage", side_effect=disco),
        mock.patch.object(menu, "_puntos_montaje", return_value=["/", "/mnt/datos"]),
        mock.patch.object(appmod.historial, "foto_de", return_value=None),
    ]
    for p in parches:
        p.start()
    try:
        estado._escribir("analisis", {"fecha": "2026-10-06T10:00:00", "seguro": 9 * GB, "revisar": 61 * GB,
                                      "cantidad": 10,
                                      "principales": [["🟡", tr("Juegos instalados por fuera de Steam"), 38 * GB]]})
        estado._escribir("limpieza", {"fecha": "2026-10-03T18:20:00", "liberado": 7 * GB, "ok": 12, "total": 12})
        demo.historial()
        asyncio.run(capturar(demo))
    finally:
        for p in reversed(parches):
            p.stop()
        shutil.rmtree(demo.tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
