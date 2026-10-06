"""ArchCleaner como una sola app: menú → flujos (analizar, limpiar, desinstalar) → vuelta al menú.

Cada flujo es una secuencia de pantallas (`push_screen_wait`) que corre en un worker. La lógica
(análisis, ficha, acciones, seguridad) está fuera de acá: esto solo encadena pantallas.
"""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual import work
from textual.app import App
from textual.binding import Binding
from textual.screen import ModalScreen

from .. import historial, timeshift
from ..acciones import Tarea, armar_tarea, ejecutar
from ..analisis import Resultado, analizar
from ..desinstalar import (SECCIONES, buscar, libre as libre_desinstalar, manifiesto_steam, panel_ficha,
                           panel_plan as plan_desinstalar, panel_verificacion, sigue_instalado, snapshot_sugerida,
                           verificar)
from ..estado import guardar_analisis, guardar_limpieza, guardar_tiempos, tiempos_previos
from ..ficha import Ficha, investigar
from ..informe import componer
from ..limpiar import armar_tareas, libre, panel_final, panel_plan
from ..modelo import Hallazgo, Limpieza, Modo, Nivel
from ..programas import listar
from ..util import humano
from .comunes import ACTUALIZAR, ESPACIO, Dialogo, Progreso, Vista
from .ejecucion import Ctx, Ejecucion, Paso
from .explorar import ElegirRaiz, ExplorarScreen
from .historial import CrecioScreen
from .menu import MenuScreen
from .mouse_lateral import activar as activar_mouse_lateral
from .plan import PlanScreen
from .programas import ElegirProgramaScreen
from .seleccion import SeleccionScreen
from ..i18n import tr

activar_mouse_lateral()

CSS = """
Screen { background: $surface; }
.cabecera { height: auto; min-height: 2; padding: 0 2; background: $panel; }
.cuerpo { height: 1fr; padding: 0 1; }
.botones { height: auto; padding: 1 1 0 1; align-horizontal: left; dock: bottom; background: $surface; }
.botones Button { margin-right: 1; min-width: 12; }
.botones .espacio { width: 1fr; }
.lista { height: 1fr; border: round $primary 40%; padding: 0 1; }
.lista:focus { border: round $primary; }
.lista > .option-list--option-disabled { color: $text; }
.info { height: auto; max-height: 9; min-height: 5; border: round $secondary 50%; padding: 0 1; }
#buscar { margin: 1 1 0 1; border: round $primary 50%; }
#buscar:focus { border: round $primary; }
#lista { margin: 0 1; }
.orden { height: 1; margin: 1 2 0 2; }

/* menú */
MenuScreen { align: center top; }
#todo { width: 100%; max-width: 110; height: auto; padding: 1 2; }
#logo { height: auto; margin: 0 0 1 1; }
#tarjetas { height: 6; }
#tarjetas > Static {
    width: 1fr; height: 100%; padding: 0 1;
    border: round $foreground 30%; border-title-color: $text; border-subtitle-color: $text-muted;
    border-title-align: left; border-subtitle-align: right;
}
#tarjetas > #t-discos { width: 2fr; }
#menu { height: auto; max-height: 12; margin-top: 1; border: round $primary 50%; padding: 0 1; }
#menu:focus { border: round $primary; }
#pie { margin: 1 0 0 1; color: $text-muted; }

/* progreso */
.progreso { width: 100%; height: 100%; align: center middle; }
.progreso-titulo, .progreso-detalle, .progreso-etapa { width: 100%; height: auto; margin: 1; text-align: center; }
.progreso-etapa { margin-bottom: 0; }
.progreso Center { height: auto; }
#barra { width: auto; margin: 1 0 0 0; }
#barra Bar { width: 50; }
#barra Bar > .bar--bar { color: $success; background: $foreground 12%; }
LoadingIndicator { height: 3; }

/* diálogos */
ModalScreen { align: center middle; background: $background 70%; }
.dialogo { width: 90; max-width: 95%; height: auto; max-height: 90%; padding: 1 2;
           border: thick $primary; background: $panel; }
.dialogo.peligro { border: thick $error; }
.dialogo-titulo { margin-bottom: 1; }
.dialogo-cuerpo { height: auto; max-height: 20; }
.dialogo .botones { dock: none; padding: 1 0 0 0; background: $panel; }
.dialogo Input { margin: 1 0 0 0; }

/* plan */
RadioSet { margin: 0 0 0 2; border: round $warning 50%; }
Checkbox { margin: 0 0 0 2; }

/* explorar */
.migas { height: 1; padding: 0 2; margin: 1 0 0 0; }
.ruta { width: 1fr; }
.resumen { width: auto; }
.barra-explorar .separador { width: 3; }
.elegir-raiz { width: 100; }
.elegir-raiz #raices { height: auto; max-height: 8; margin-bottom: 1; border: round $primary 50%; }
.elegir-raiz #raices:focus { border: round $primary; }
.barra-explorar Button { min-width: 10; margin-right: 1; }

/* ejecución */
#progreso { margin: 1 2 0 2; }
.actual { height: auto; padding: 0 2; margin-top: 1; }
.log { height: 1fr; margin: 0 1; border: round $primary 40%; }
"""


class ArchCleanerApp(App[None]):
    TITLE = "ArchCleaner"
    CSS = CSS
    # Botones laterales del mouse (ver mouse_lateral.py) y su equivalente con teclado.
    BINDINGS = [
        Binding("alt+left", "atras", tr("Atrás"), show=False, priority=True),
        Binding("alt+right", "adelante", tr("Adelante"), show=False, priority=True),
    ]

    def __init__(self, inicio: str = "menu", programa: str | None = None, simulacro: bool = False):
        super().__init__()
        self.inicio, self.programa_inicial, self.simulacro_inicial = inicio, programa, simulacro
        self.resultado: Resultado | None = None  # último análisis de esta sesión (lo reusa Explorar)
        self.foto_anterior: historial.Foto | None = None  # la foto del historial anterior a ese análisis

    def action_atras(self) -> None:
        """◀ Atrás: cada pantalla sabe qué es "atrás" para ella; las ventanas emergentes se cierran."""
        pantalla = self.screen
        if hasattr(pantalla, "action_atras"):
            pantalla.action_atras()
        elif isinstance(pantalla, ModalScreen):
            pantalla.dismiss(None)

    def action_adelante(self) -> None:
        if hasattr(self.screen, "action_adelante"):
            self.screen.action_adelante()

    def on_mount(self) -> None:
        self.push_screen(MenuScreen())
        if self.inicio != "menu":
            self.iniciar(self.inicio, self.programa_inicial, self.simulacro_inicial)

    def iniciar(self, opcion: str, programa: str | None = None, simulacro: bool = False) -> None:
        if opcion == "analizar":
            self.flujo_analizar()
        elif opcion in ("limpiar", "simulacro"):
            self.flujo_limpiar(simulacro or opcion == "simulacro")
        elif opcion == "desinstalar":
            self.flujo_desinstalar(programa, simulacro)
        elif opcion == "actualizar":
            self.flujo_actualizar()
        elif opcion == "explorar":
            self.flujo_explorar(programa)
        elif opcion == "crecio":
            self.flujo_crecio()

    # ── ayudantes ──

    async def _con_progreso(self, titulo: str, funcion, *args, **kwargs):
        """Corre `funcion` en un hilo mostrando una pantalla de progreso."""
        prog = Progreso(titulo)
        await self.push_screen(prog)
        try:
            return await asyncio.to_thread(funcion, *args, **kwargs)
        finally:
            prog.dismiss()

    async def _analizar(self) -> Resultado:
        prog = Progreso(tr("🔍 Analizando el disco…"), barra=True)
        await self.push_screen(prog)
        try:
            res = await asyncio.to_thread(
                analizar, True, avance=lambda f, e, d: self.call_from_thread(prog.avanzar, f, e, d),
                previos=tiempos_previos())
        finally:
            prog.dismiss()
        guardar_tiempos(res.tiempos)
        guardar_analisis(res.hallazgos)
        foto = historial.foto_de(res)
        if foto:
            historial.guardar(foto)
            self.foto_anterior = historial.anterior(foto.fecha)
        self.resultado = res
        return res

    def _comparacion(self):
        """Lo que cambió desde el análisis anterior (para la tarjeta del informe), si hay con qué comparar."""
        foto = historial.ultima()
        if not foto or not self.foto_anterior:
            return None
        return historial.comparar(self.foto_anterior, foto)

    # ── analizar ──

    @work(exclusive=True, group="flujo")
    async def flujo_actualizar(self) -> None:
        await self._analizar()
        self.notify(tr("Datos actualizados."), title=tr("🔄 Actualizar"))

    @work(exclusive=True, group="flujo")
    async def flujo_analizar(self) -> None:
        res = await self._analizar()
        while True:
            r = await self.push_screen_wait(Vista(
                tr("🔍 Análisis de disco"), componer(res, pie=False, comparacion=self._comparacion()),
                [("limpiar", tr("🧹 Limpiar ahora"), "success"), ESPACIO, ACTUALIZAR,
                 ("volver", tr("🏠 Inicio"), "default")],
                tr("Solo lectura: no se borró nada. Rueda del mouse o flechas para recorrer.")))
            if r == "actualizar":
                res = await self._analizar()
                continue
            if r == "limpiar" and await self._limpiar(res, simulacro=False) == "atras":
                continue  # desde la lista para tildar, «atrás» vuelve al informe
            break

    # ── explorar ──

    @work(exclusive=True, group="flujo")
    async def flujo_explorar(self, ruta: str | None = None) -> None:
        import os
        res = self.resultado or await self._analizar()
        if ruta:
            ruta = os.path.realpath(os.path.expanduser(ruta))
            if not os.path.isdir(ruta):
                self.notify(tr("No existe la carpeta {ruta}", ruta=ruta), severity="error")
                return
        else:
            ruta = await self.push_screen_wait(ElegirRaiz(res))
            if not ruta:
                return
        await self.push_screen_wait(ExplorarScreen(res, ruta, self.foto_anterior))

    # ── qué creció ──

    @work(exclusive=True, group="flujo")
    async def flujo_crecio(self) -> None:
        while True:
            foto = historial.ultima()
            if foto is None or len(historial.listar()) < 2:
                r = await self.push_screen_wait(Vista(
                    tr("📈 Qué creció"), [historial.sin_historial(len(historial.listar()))],
                    [("actualizar", tr("🔍 Analizar ahora"), "primary"), ESPACIO, ("volver", tr("🏠 Inicio"), "default")]))
            else:
                r = await self.push_screen_wait(CrecioScreen(foto))
            if r != "actualizar":
                return
            await self._analizar()

    # ── limpiar ──

    @work(exclusive=True, group="flujo")
    async def flujo_limpiar(self, simulacro: bool = False) -> None:
        await self._limpiar(await self._analizar(), simulacro)

    async def _limpiar(self, res: Resultado, simulacro: bool) -> str | None:
        """Devuelve "atras" si el usuario volvió atrás desde la primera pantalla."""
        sel = None
        while True:
            sel = await self.push_screen_wait(SeleccionScreen(res.hallazgos, previa=sel))
            if sel == "actualizar":
                res, sel = await self._analizar(), None
                continue
            if sel == "atras":
                return "atras"
            if not sel:
                return None
            tareas = armar_tareas(res.hallazgos, sel)
            if not tareas:
                self.notify(tr("No quedó nada elegido."))
                continue
            decision = await self.push_screen_wait(PlanScreen(
                tr("📝 Plan de limpieza"), panel_plan(tareas), tareas, simulacro=simulacro))
            if decision == "atras":
                continue  # vuelve a la lista con lo que habías tildado
            if decision is None:
                return None
            break
        antes = libre(tareas)

        def final(ctx: Ctx, oks: list[bool]) -> list:
            from types import SimpleNamespace
            resultados = [SimpleNamespace(ok=ok) for ok in oks]
            panel = panel_final(tareas, resultados, antes)
            liberado = sum(max(0, d) for d in _liberado(antes).values())
            guardar_limpieza(liberado, sum(oks), len(tareas))
            return [Text(""), panel]

        pasos = [Paso(t.hallazgo.titulo, lambda ctx, t=t: _hacer_tarea(ctx, t)) for t in tareas]
        await self.push_screen_wait(Ejecucion(tr("🧹 Limpiando"), pasos, final))

    # ── desinstalar ──

    @work(exclusive=True, group="flujo")
    async def flujo_desinstalar(self, busqueda: str | None = None, simulacro: bool = False) -> None:
        programas = await self._con_progreso(tr("📦 Buscando programas instalados…"), listar)
        prog = buscar(programas, busqueda)
        # Pasos: buscar → ficha → restos → plan. «◀ Atrás» vuelve al paso anterior; 🔄 vuelve a investigar.
        paso = "ficha" if prog else "buscar"
        ficha: Ficha | None = None
        sel: dict | None = None
        while True:
            if paso == "buscar":
                prog = await self.push_screen_wait(ElegirProgramaScreen(programas, busqueda or ""))
                if prog == "actualizar":
                    programas = await self._con_progreso(tr("📦 Buscando programas instalados…"), listar)
                    continue
                if prog is None:
                    return
                paso, ficha, sel = "ficha", None, None

            elif paso == "ficha":
                if ficha is None:
                    ficha = await self._con_progreso(tr("🔎 Investigando {nombre}…", nombre=prog.nombre), investigar, prog)
                    if not sigue_instalado(prog):
                        self.notify(tr("{nombre} ya no está instalado.", nombre=prog.nombre), severity="warning")
                        return
                botones = [ESPACIO, ACTUALIZAR, ("volver", tr("🏠 Inicio"), "default")] if ficha.bloqueo else \
                    [("seguir", tr("Seguir ▸"), "primary"), ESPACIO, ACTUALIZAR, ("volver", tr("Cancelar"), "default")]
                r = await self.push_screen_wait(Vista(
                    tr("📦 Desinstalar {nombre}", nombre=prog.nombre), [panel_ficha(ficha)], botones,
                    tr("Ficha: todo lo que se va y todo lo que dejaría. No se tocó nada.")))
                if r == "actualizar":
                    ficha, sel = None, None
                    continue
                if r == "atras":
                    paso = "buscar"
                    continue
                if r != "seguir":
                    return
                paso = "restos" if ficha.restos else "plan"

            elif paso == "restos":
                s = await self.push_screen_wait(SeleccionScreen(
                    ficha.restos, tr("📦 {nombre}: ¿qué restos borro?", nombre=prog.nombre), SECCIONES, previa=sel))
                if s == "actualizar":
                    paso, ficha, sel = "ficha", None, None
                    continue
                if s == "atras":
                    paso = "ficha"
                    continue
                if s is None:
                    return
                sel, paso = s, "plan"

            elif paso == "plan":
                restos = armar_tareas(ficha.restos, sel or {})
                decision = await self.push_screen_wait(PlanScreen(
                    tr("📝 Plan: desinstalar {nombre}", nombre=prog.nombre), plan_desinstalar(ficha, restos), restos,
                    simulacro=simulacro, snapshot=snapshot_sugerida(ficha),
                    boton=tr("📦 Desinstalar {nombre}", nombre=prog.nombre)))
                if decision == "atras":
                    paso = "restos" if ficha.restos else "ficha"
                    continue
                if decision is None:
                    return
                break

        antes = libre_desinstalar()
        pasos = _pasos_desinstalar(ficha, restos, decision.snapshot)

        def final(ctx: Ctx, oks: list[bool]) -> list:
            if len(oks) < len(pasos):  # se detuvo en un paso crítico (la desinstalación en sí)
                return [Text(tr("\nLa desinstalación no se completó: no toqué los restos."), style="bold yellow")]
            v = verificar(ficha, restos, antes)
            if v.nuevos and ctx.preguntar(Dialogo(
                    tr("Aparecieron restos nuevos"),
                    Text(tr("Después de desinstalar quedaron cosas que antes eran del paquete (pacman deja las "
                           "carpetas con archivos que no son suyos):\n\n") +
                         "\n".join(f"  {humano(i.peso):>9}  {i.nombre}" for h in v.nuevos for i in h.detalle)),
                    [("borrar", tr("🗑 Borrarlos también"), "warning"), ("dejar", tr("Dejarlos"), "default")])) == "borrar":
                for h in v.nuevos:
                    t = armar_tarea(h, list(range(len(h.detalle))))
                    _hacer_tarea(ctx, t)
                v = verificar(ficha, restos, antes)
            return [Text(""), panel_verificacion(v, prog.nombre)]

        await self.push_screen_wait(Ejecucion(tr("📦 Desinstalando {nombre}", nombre=prog.nombre), pasos, final))


# ── Pasos ────────────────────────────────────────────────────────────────────

def _liberado(antes: dict[str, int]) -> dict[str, int]:
    import shutil
    return {p: shutil.disk_usage(p).free - libre for p, libre in antes.items()}


def _hacer_tarea(ctx: Ctx, t: Tarea) -> tuple[bool, str]:
    r = ejecutar(t, ctx.verif, salida=lambda s: ctx.log(s), correr=ctx.correr)
    for e in r.errores[:8]:
        ctx.log(f"    {e}", "yellow")
    if len(r.errores) > 8:
        ctx.log("    " + tr("… y {n} errores más (ver el log)", n=len(r.errores) - 8), "yellow")
    return r.ok, r.mensaje


def _tarea_comando(titulo: str, comandos: list[list[str]], sudo: bool) -> Tarea:
    h = Hallazgo(tr("Desinstalar"), titulo, Nivel.SEGURO, 0, "", limpieza=Limpieza(Modo.COMANDO, comandos, sudo=sudo))
    return armar_tarea(h)


def _pasos_desinstalar(ficha: Ficha, restos: list[Tarea], snapshot: bool) -> list[Paso]:
    prog = ficha.programa
    pasos: list[Paso] = []
    if snapshot:
        def hacer_snapshot(ctx: Ctx) -> tuple[bool, str]:
            ctx.log(tr("  puede tardar unos minutos…"))
            if ctx.correr(["sudo", *timeshift.comando_crear(tr("antes de desinstalar {nombre}", nombre=prog.nombre))]) == 0:
                return True, tr("snapshot creada")
            seguir = ctx.preguntar(Dialogo(tr("No se pudo crear la snapshot"), Text(tr("¿Seguir igual sin snapshot?")),
                                           [("si", tr("Seguir sin snapshot"), "warning"),
                                            ("no", tr("Cancelar"), "default")]))
            return seguir == "si", tr("sigo sin snapshot") if seguir == "si" else "cancelado"
        pasos.append(Paso(tr("🕒 Snapshot de Timeshift"), hacer_snapshot, critico=True))

    for s in ficha.servicios:
        cmd = ["systemctl", *(["--user"] if s.usuario else []), "disable", "--now", s.unidad]
        t = _tarea_comando(tr("Apagar {unidad}", unidad=s.unidad), [cmd], sudo=not s.usuario)
        pasos.append(Paso(tr("⚙️  Apagar el servicio {unidad}", unidad=s.unidad), lambda ctx, t=t: _hacer_tarea(ctx, t)))

    if prog.origen == "steam":
        def hacer_steam(ctx: Ctx) -> tuple[bool, str]:
            import subprocess
            subprocess.run(["xdg-open", f"steam://uninstall/{prog.id}"], capture_output=True)
            manifiesto = manifiesto_steam(prog)
            ctx.log(tr("  esperando a que Steam borre {archivo}…", archivo=manifiesto.name))
            # Steam borra el appmanifest_<appid>.acf al terminar de desinstalar: eso es la señal.
            r = ctx.esperar(Dialogo(
                tr("⏳ Esperando a Steam: {nombre}", nombre=prog.nombre),
                Text.assemble(
                    tr("Se abrió Steam con su ventana de desinstalación. "), (tr("Confirmá ahí."), "bold"), "\n\n",
                    (tr("ArchCleaner se da cuenta solo cuando Steam termina y sigue con la limpieza."), "dim")),
                [("cancelar", tr("Cancelar"), "default")]),
                listo=lambda: not manifiesto.exists())
            if r != "auto":
                return False, tr("cancelado (el juego sigue instalado)")
            return True, tr("Steam lo desinstaló (detectado automáticamente)")
        pasos.append(Paso(tr("🎮 Desinstalar {nombre} (Steam)", nombre=prog.nombre), hacer_steam, critico=True))
    elif prog.origen != "appimage":
        t = _tarea_comando(tr("Desinstalar {nombre}", nombre=prog.nombre), ficha.comandos, ficha.sudo)

        def hacer_principal(ctx: Ctx, t=t) -> tuple[bool, str]:
            ok, msg = _hacer_tarea(ctx, t)
            if sigue_instalado(prog):
                return False, tr("sigue instalado") + (f" ({msg})" if not ok else tr(" (¿cancelaste en pacman?)"))
            return True, "desinstalado"
        pasos.append(Paso(tr("📦 Desinstalar {nombre}", nombre=prog.nombre), hacer_principal, critico=True))

    for t in restos:
        pasos.append(Paso(f"{t.hallazgo.nivel.icono} {t.hallazgo.titulo}", lambda ctx, t=t: _hacer_tarea(ctx, t)))
    return pasos
