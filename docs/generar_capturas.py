"""Genera las capturas del README (docs/capturas/*.svg) con una PC de demostración.

Nada sale de tu PC: el home, los discos, los programas y el historial son inventados, y no se
borra ni se instala nada (no se aprieta ningún botón que ejecute).

    python docs/generar_capturas.py
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

from archcleaner import estado, historial  # noqa: E402
from archcleaner.analisis import Resultado  # noqa: E402
from archcleaner.contexto import Contexto  # noqa: E402
from archcleaner.escaner import ResultadoEscaneo  # noqa: E402
from archcleaner.modelo import Hallazgo, Item, Limpieza, Modo, Nivel  # noqa: E402
from archcleaner.programas import Programa  # noqa: E402
from archcleaner.tui import app as appmod  # noqa: E402
from archcleaner.tui import menu  # noqa: E402
from archcleaner.tui.app import ArchCleanerApp  # noqa: E402

SALIDA = RAIZ / "docs/capturas"
TAMANO = (112, 36)
GB, MB = 1024**3, 1024**2
DIA = 86400
Uso = namedtuple("Uso", "total used free")


def disco(_ruta) -> Uso:
    return Uso(500 * GB, 342 * GB, 158 * GB)


class Demo:
    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="archcleaner-demo-"))
        self.home = self.tmp / "home/usuario"
        h = self.home
        for rel in (".cache/mesa_shader_cache", ".cache/google-chrome", ".cache/thumbnails", ".cache/pip",
                    ".local/share/Steam/steamapps/common", ".local/share/Steam/steamapps/workshop",
                    ".config", "Descargas/isos", "Juegos/Hollow Knight", "Videos/2025", "Proyectos/web/node_modules",
                    "Documentos", "Imágenes"):
            (h / rel).mkdir(parents=True, exist_ok=True)
        (h / "Descargas/ubuntu-24.04-desktop-amd64.iso").write_bytes(b"x" * 4096)
        (h / "Videos/2025/vacaciones.mp4").write_bytes(b"x" * 4096)
        self.estado = self.tmp / "estado"

    def escaneo(self) -> ResultadoEscaneo:
        h = str(self.home)
        total = {
            h: 182 * GB, f"{h}/.local": 96 * GB, f"{h}/.local/share": 95 * GB, f"{h}/.local/share/Steam": 88 * GB,
            f"{h}/.local/share/Steam/steamapps": 87 * GB, f"{h}/.local/share/Steam/steamapps/common": 79 * GB,
            f"{h}/.local/share/Steam/steamapps/workshop": 6 * GB, f"{h}/Juegos": 38 * GB,
            f"{h}/Juegos/Hollow Knight": 38 * GB, f"{h}/Videos": 21 * GB, f"{h}/Videos/2025": 21 * GB,
            f"{h}/Descargas": 9 * GB, f"{h}/Descargas/isos": 3 * GB, f"{h}/.cache": 4 * GB,
            f"{h}/.cache/mesa_shader_cache": 1600 * MB, f"{h}/.cache/google-chrome": 1200 * MB,
            f"{h}/.cache/thumbnails": 700 * MB, f"{h}/.cache/pip": 500 * MB, f"{h}/Proyectos": 2 * GB,
            f"{h}/Proyectos/web": 2 * GB, f"{h}/Proyectos/web/node_modules": 1800 * MB, f"{h}/.config": 3 * GB,
            f"{h}/Documentos": 2 * GB, f"{h}/Imágenes": 6 * GB,
        }
        return ResultadoEscaneo(raiz=h, total=total)

    def resultado(self) -> Resultado:
        ctx = Contexto(home=self.home)
        ctx.escaneos = [self.escaneo()]
        h = self.home
        H = [
            Hallazgo("Pacman", "Caché de paquetes de pacman", Nivel.SEGURO, 3400 * MB,
                     "Instaladores de versiones viejas. Se dejan las 2 últimas de cada paquete (por si "
                     "tenés que volver atrás) y se borra el resto con paccache.",
                     rutas=[Path("/var/cache/pacman/pkg")],
                     limpieza=Limpieza(Modo.COMANDO, [["paccache", "-rk2"]], sudo=True)),
            Hallazgo("Home", "Caché de programas (~/.cache)", Nivel.SEGURO, 4000 * MB,
                     "Archivos temporales que los programas regeneran solos.",
                     rutas=[h / ".cache"], detalle=[
                         Item("mesa_shader_cache", 1600 * MB, h / ".cache/mesa_shader_cache"),
                         Item("google-chrome", 1200 * MB, h / ".cache/google-chrome"),
                         Item("thumbnails", 700 * MB, h / ".cache/thumbnails"),
                         Item("pip", 500 * MB, h / ".cache/pip")],
                     limpieza=Limpieza(Modo.BORRAR, por_item=True)),
            Hallazgo("Sistema", "Logs viejos del sistema (journald)", Nivel.SEGURO, 1100 * MB,
                     "Se recortan a los 200 MB más recientes.", rutas=[Path("/var/log/journal")],
                     limpieza=Limpieza(Modo.COMANDO, [["journalctl", "--vacuum-size=200M"]], sudo=True)),
            Hallazgo("Pacman", "Paquetes huérfanos", Nivel.SEGURO, 640 * MB,
                     "Dependencias que quedaron instaladas y ya nadie usa.",
                     detalle=[Item("python-sphinx", 210 * MB), Item("rust", 400 * MB), Item("go-tools", 30 * MB)],
                     limpieza=Limpieza(Modo.COMANDO, [["pacman", "-Rns", "python-sphinx", "rust", "go-tools"]],
                                       sudo=True)),
            Hallazgo("Archivos", "Juegos instalados por fuera de Steam", Nivel.REVISAR, 38 * GB,
                     "No es basura: son juegos instalados a mano. Si ya no jugás alguno, borrar su carpeta "
                     "libera todo eso.", rutas=[h / "Juegos/Hollow Knight"],
                     detalle=[Item("Hollow Knight  (~/Juegos)", 38 * GB, h / "Juegos/Hollow Knight")],
                     limpieza=Limpieza(Modo.PAPELERA, por_item=True)),
            Hallazgo("Sistema", "Snapshots de Timeshift de más de 30 días", Nivel.REVISAR, 12 * GB,
                     "Las snapshots manuales no se borran solas. La más reciente se conserva siempre.",
                     detalle=[Item("2026-06-02_10-00-01  (manual, hace 126 días)", 7 * GB, comando=["true"]),
                              Item("2026-08-14_18-30-00  (manual, hace 53 días)", 5 * GB, comando=["true"])],
                     limpieza=Limpieza(Modo.COMANDO, sudo=True, por_item=True)),
            Hallazgo("Steam", "Workshop de Wallpaper Engine", Nivel.REVISAR, 6 * GB,
                     "Contenido de Workshop al que estás suscripto. Si lo borrás a mano, Steam lo vuelve a "
                     "bajar: desuscribite en Steam de lo que no uses.",
                     rutas=[h / ".local/share/Steam/steamapps/workshop"], suma=False, detalle=[
                         Item("Neon City Rain 4K  (2891734455)", 2100 * MB), Item("Lofi Room  (1981236612)", 900 * MB),
                         Item("Aurora Borealis  (2311898720)", 640 * MB)]),
            Hallazgo("Home", "Descargas de hace más de 90 días", Nivel.REVISAR, 3 * GB,
                     "Instaladores, ISOs, comprimidos... cosas que bajaste hace rato.",
                     rutas=[h / "Descargas/ubuntu-24.04-desktop-amd64.iso"],
                     detalle=[Item("ubuntu-24.04-desktop-amd64.iso", 3 * GB,
                                   h / "Descargas/ubuntu-24.04-desktop-amd64.iso")],
                     limpieza=Limpieza(Modo.PAPELERA, por_item=True)),
            Hallazgo("Desarrollo", "Dependencias de proyectos (node_modules / venv)", Nivel.REVISAR, 1800 * MB,
                     "Se regeneran con `npm install`.", rutas=[h / "Proyectos/web/node_modules"],
                     detalle=[Item("~/Proyectos/web/node_modules  (sin tocar hace 140 días)", 1800 * MB,
                                   h / "Proyectos/web/node_modules")],
                     limpieza=Limpieza(Modo.PAPELERA, por_item=True)),
            Hallazgo("Steam", "Juegos instalados en ~/.local/share/Steam", Nivel.INFO, 79 * GB,
                     "Lo que pesa cada juego. Si alguno no lo jugás más, desinstalalo desde Steam.",
                     detalle=[Item("Cyberpunk 2077", 65 * GB), Item("Hades II", 9 * GB), Item("Terraria", 5 * GB)],
                     suma=False),
        ]
        for i, x in enumerate(H, 1):
            x.numero = i
        ctx.etiquetas[str(h / ".local/share/Steam/steamapps/common")] = "juegos de Steam"
        return Resultado(ctx, H)

    def programas(self) -> list[Programa]:
        ahora = time.time()

        def p(id_, nombre, origen, gb, desc, uso_dias, inst_dias=200, conocido=True):
            return Programa(id_, nombre, origen, int(gb * GB), desc,
                            ultimo_uso=ahora - uso_dias * DIA if uso_dias is not None else None,
                            instalado=ahora - inst_dias * DIA, uso_conocido=conocido)
        return [
            p("1091500", "Cyberpunk 2077", "steam", 65, "juego · appid 1091500 · ~/.local/share/Steam", 210),
            p("1145350", "Hades II", "steam", 9, "juego · appid 1145350 · ~/.local/share/Steam", 2),
            p("android-studio", "android-studio", "aur", 2.9, "The official Android IDE", None, 300),
            p("libreoffice-fresh", "libreoffice-fresh", "repo", 1.4, "LibreOffice branch with new features", 45),
            p("com.spotify.Client", "Spotify", "flatpak", 0.9, "com.spotify.Client", 0),
            p("blender", "blender", "repo", 0.8, "A fully integrated 3D graphics creation suite", 380, 400),
            p("gimp", "gimp", "repo", 0.4, "GNU Image Manipulation Program", 12),
            p("obs-studio", "obs-studio", "repo", 0.2, "Free and open source software for video recording", 30),
            p("/home/usuario/Aplicaciones/Krita.AppImage", "Krita", "appimage", 0.3, "~/Aplicaciones/Krita.AppImage",
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
                cambios |= {f"{h}/Juegos": 0, f"{h}/Juegos/Hollow Knight": 0,
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
                                      "cantidad": 10, "principales": [["🟡", "Juegos instalados por fuera de Steam",
                                                                       38 * GB]]})
        estado._escribir("limpieza", {"fecha": "2026-10-03T18:20:00", "liberado": 7 * GB, "ok": 12, "total": 12})
        demo.historial()
        asyncio.run(capturar(demo))
    finally:
        for p in reversed(parches):
            p.stop()
        shutil.rmtree(demo.tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
