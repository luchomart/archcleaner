"""Pantalla de ejecución: corre los pasos de a uno, muestra la salida en vivo y el resultado al final.

Los pasos corren en un hilo aparte (la pantalla sigue respondiendo). Dos cosas se hacen en la terminal
de verdad, con la app suspendida un momento: pedir la contraseña de sudo, y pacman (que muestra lo que
quita y pide su propia confirmación). Al terminar, la app vuelve sola.
"""

from __future__ import annotations

import subprocess
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass

from rich.text import Text
from textual.app import ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, ProgressBar, RichLog, Static

from ..seguridad import Verificador
from .comunes import ESPACIO, barra_botones, cabecera
from ..i18n import tr


@dataclass
class Paso:
    titulo: str
    hacer: Callable[["Ctx"], tuple[bool, str]]
    critico: bool = False   # si falla, no se hacen los pasos siguientes


class Ctx:
    """Lo que un paso puede usar: escribir en el log, correr comandos, preguntar con una ventana."""

    def __init__(self, pantalla: "Ejecucion"):
        self.pantalla = pantalla
        self.app = pantalla.app
        self.verif = Verificador()

    def log(self, texto, estilo: str = "grey62") -> None:
        contenido = Text(texto, style=estilo) if isinstance(texto, str) else texto
        self.app.call_from_thread(self.pantalla.query_one(RichLog).write, contenido)

    def preguntar(self, pantalla):
        """Abre una ventana (Dialogo, etc.) y espera la respuesta. Se llama desde el hilo de los pasos."""
        listo, caja = threading.Event(), {}

        def al_cerrar(resultado) -> None:
            caja["r"] = resultado
            listo.set()

        self.app.call_from_thread(self.app.push_screen, pantalla, al_cerrar)
        listo.wait()
        return caja.get("r")

    def esperar(self, pantalla, listo: Callable[[], bool], cada: float = 1.0):
        """Muestra una ventana mientras espera a que `listo()` sea verdadero (se revisa cada `cada` segundos).

        Si se cumple, la ventana se cierra sola y devuelve "auto". Si el usuario aprieta un botón antes,
        devuelve el id de ese botón.
        """
        respondio, caja = threading.Event(), {}

        def al_cerrar(resultado) -> None:
            caja.setdefault("r", resultado)
            respondio.set()

        self.app.call_from_thread(self.app.push_screen, pantalla, al_cerrar)
        while not respondio.wait(cada):
            if listo():
                caja["r"] = "auto"
                self.app.call_from_thread(pantalla.dismiss, "auto")
                respondio.wait()
                break
        return caja.get("r")

    def en_terminal(self, cmd: list[str], aviso: str) -> int:
        """Corre `cmd` en la terminal real (la app se aparta un momento y vuelve sola)."""
        def hacer() -> int:
            try:
                with self.app.suspend():
                    print(f"\n\033[1;36m── ArchCleaner ──\033[0m {aviso}\n", flush=True)
                    return subprocess.run(cmd).returncode
            except SuspendNotSupported:
                self.log(tr("  Esta terminal no permite apartar la app para responder: corré el comando a mano:\n  ")
                         + " ".join(cmd), "yellow")
                return 1
        return self.app.call_from_thread(hacer)

    def asegurar_sudo(self) -> bool:
        if subprocess.run(["sudo", "-n", "-v"], capture_output=True).returncode == 0:
            return True
        return self.en_terminal(["sudo", "-v"], tr("🔐 Necesito permisos de administrador: escribí tu contraseña.")) == 0

    def correr(self, cmd: list[str]) -> int:
        """Runner para acciones.ejecutar: pacman va a la terminal; el resto se muestra en el log."""
        con_sudo = cmd[0] == "sudo"
        programa = cmd[1] if con_sudo else cmd[0]
        if programa == "pacman":
            return self.en_terminal(cmd, tr("pacman te muestra lo que quita y pide confirmación. "
                                            "Después ArchCleaner vuelve solo."))
        if con_sudo:
            if not self.asegurar_sudo():
                self.log(tr("  sin permisos de administrador: salteado"), "yellow")
                return 1
            cmd = ["sudo", "-n", *cmd[1:]]
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                 text=True, bufsize=1)
        except OSError as e:
            self.log(f"  {e}", "yellow")
            return 127
        assert p.stdout
        for linea in p.stdout:
            if linea.strip():
                self.log("  " + linea.rstrip()[:200])
        return p.wait()


class Ejecucion(Screen[None]):
    BINDINGS = [Binding("escape", "volver", tr("Volver"), show=False)]

    def __init__(self, titulo: str, pasos: list[Paso], al_terminar: Callable[[Ctx, list[bool]], list] | None = None):
        super().__init__()
        self.titulo, self.pasos, self.al_terminar = titulo, pasos, al_terminar
        self.terminado = False

    def compose(self) -> ComposeResult:
        yield cabecera(self.titulo, tr("Trabajando… no cierres la terminal."))
        yield ProgressBar(total=len(self.pasos), show_eta=False, id="progreso")
        yield Static("", id="actual", classes="actual")
        yield RichLog(wrap=True, id="log", classes="log")
        yield barra_botones([("menu", tr("🏠 Inicio"), "primary"), ESPACIO, ("salir", tr("Salir"), "default")])

    def on_mount(self) -> None:
        for b in self.query(Button):
            b.disabled = True
        self.run_worker(self._correr, thread=True)

    def _correr(self) -> None:
        ctx = Ctx(self)
        oks: list[bool] = []
        for i, paso in enumerate(self.pasos, 1):
            self.app.call_from_thread(self.query_one("#actual", Static).update,
                                      Text.assemble((f"[{i}/{len(self.pasos)}] ", "dim"), (paso.titulo, "bold")))
            ctx.log(Text.assemble(("\n▸ ", "cyan"), (paso.titulo, "bold")))
            try:
                ok, mensaje = paso.hacer(ctx)
            except Exception:  # un paso roto no tiene que colgar la pantalla
                ok, mensaje = False, tr("error inesperado:\n") + traceback.format_exc(limit=3)
            oks.append(ok)
            ctx.log(("  ✔ " if ok else "  ✘ ") + mensaje, "green" if ok else "yellow")
            self.app.call_from_thread(self.query_one("#progreso", ProgressBar).advance, 1)
            if not ok and paso.critico:
                ctx.log(tr("\nEse paso era necesario para seguir: me detengo acá."), "bold yellow")
                break
        if self.al_terminar:
            try:
                for r in self.al_terminar(ctx, oks):
                    ctx.log(r)
            except Exception:
                ctx.log(tr("error al terminar:\n") + traceback.format_exc(limit=3), "yellow")
        self.app.call_from_thread(self._fin, all(oks) and len(oks) == len(self.pasos))

    def _fin(self, todo_ok: bool) -> None:
        self.terminado = True
        self.query_one("#actual", Static).update(
            Text(tr("✅ Listo.") if todo_ok else tr("⚠ Terminó con avisos: revisá el detalle."),
                 style="bold green" if todo_ok else "bold yellow"))
        for b in self.query(Button):
            b.disabled = False
        self.query_one("#menu", Button).focus()

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "salir":
            self.app.exit()
        else:
            self.dismiss(None)

    def action_volver(self) -> None:
        if self.terminado:
            self.dismiss(None)

    def action_atras(self) -> None:
        self.action_volver()
