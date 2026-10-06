"""Ejecuta las limpiezas que eligió el usuario. Es el único módulo que borra cosas.

Cada tarea pasa por `seguridad.Verificador` antes de tocar el disco, y todo queda anotado en
~/.local/state/archcleaner/acciones.log (una línea JSON por acción).
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .modelo import Hallazgo, Modo
from .seguridad import Verificador

LOG = Path.home() / ".local/state/archcleaner/acciones.log"


@dataclass
class Tarea:
    hallazgo: Hallazgo
    rutas: list[Path] = field(default_factory=list)  # lo elegido (para BORRAR/VACIAR/PAPELERA)
    peso: int = 0
    comandos: list[list[str]] = field(default_factory=list)  # para COMANDO (los de los ítems elegidos o los del hallazgo)
    definitivo: bool = False  # lo que iba a la papelera se borra de verdad (el usuario lo confirmó)

    @property
    def modo(self) -> Modo:
        modo = self.hallazgo.limpieza.modo  # type: ignore[union-attr]
        return Modo.BORRAR if self.definitivo and modo == Modo.PAPELERA else modo

    def peso_de(self, ruta: Path) -> int | None:
        return next((i.peso for i in self.hallazgo.detalle if i.ruta == ruta), None)

    @property
    def sudo(self) -> bool:
        return self.hallazgo.limpieza.sudo  # type: ignore[union-attr]


@dataclass
class Resultado:
    tarea: Tarea
    ok: bool
    mensaje: str
    errores: list[str] = field(default_factory=list)


def armar_tarea(h: Hallazgo, elegidos: list[int] | None = None) -> Tarea:
    """`elegidos` = índices del detalle (solo para hallazgos por_item)."""
    assert h.limpieza
    if h.limpieza.por_item:
        items = [h.detalle[i] for i in (elegidos or []) if h.detalle[i].elegible]
        return Tarea(h, [i.ruta for i in items if i.ruta], sum(i.peso or 0 for i in items),
                     comandos=[i.comando for i in items if i.comando])
    return Tarea(h, list(h.rutas), h.peso or 0, comandos=list(h.limpieza.comandos))


def procesos_abiertos(nombres: list[str]) -> list[str]:
    return [n for n in nombres if subprocess.run(["pgrep", "-x", n], capture_output=True).returncode == 0]


# ── Ejecución ────────────────────────────────────────────────────────────────

# Cómo se corre un comando ya armado (con "sudo" adelante si hace falta). Devuelve el código de salida.
# Por defecto habla directo con la terminal; la app de textual pasa el suyo.
Correr = Callable[[list[str]], int]


def _correr_en_terminal(cmd: list[str]) -> int:
    return subprocess.run(cmd).returncode


def ejecutar(tarea: Tarea, verif: Verificador, salida: Callable[[str], None] = print,
             correr: Correr = _correr_en_terminal) -> Resultado:
    lim = tarea.hallazgo.limpieza
    assert lim
    if abiertos := procesos_abiertos(lim.cerrar):
        return _registrar(Resultado(tarea, False, f"salteado: cerrá {', '.join(abiertos)} y volvé a intentar"))

    if tarea.modo == Modo.COMANDO:
        res = _comandos(tarea, verif, correr)
    else:
        res = _rutas(tarea, verif, salida)
    return _registrar(res)


def _rutas(tarea: Tarea, verif: Verificador, salida: Callable[[str], None]) -> Resultado:
    errores: list[str] = []
    hechos = no_estaban = 0
    for ruta in tarea.rutas:
        if not os.path.lexists(ruta):
            no_estaban += 1  # lo borraste a mano (o lo borró otra cosa) después del análisis: no es un error
            salida(f"  {ruta}  (ya no estaba)")
            continue
        objetivos = _contenido(ruta) if tarea.modo == Modo.VACIAR else [ruta]
        if tarea.modo == Modo.VACIAR and (motivo := verif.problema(ruta, vaciar=True)):
            errores.append(f"{ruta}: {motivo}")
            continue
        for obj in objetivos:
            if not os.path.lexists(obj):
                continue
            if motivo := verif.problema(obj):
                errores.append(f"{obj}: {motivo}")
                continue
            try:
                if tarea.modo == Modo.PAPELERA:
                    _a_papelera(obj)
                else:
                    _borrar(obj)
                hechos += 1
            except (OSError, subprocess.CalledProcessError) as e:
                errores.append(f"{obj}: {e}")
        salida(f"  {ruta}")
    verbo = "a la papelera" if tarea.modo == Modo.PAPELERA else "borrados"
    mensaje = f"{hechos} elementos {verbo}" + (f" · {no_estaban} ya no estaban" if no_estaban else "")
    return Resultado(tarea, not errores, mensaje, errores)


def _contenido(carpeta: Path) -> list[Path]:
    try:
        return sorted(carpeta.iterdir())
    except OSError:
        return []


def _borrar(ruta: Path) -> None:
    if ruta.is_dir() and not ruta.is_symlink():
        shutil.rmtree(ruta, onexc=lambda funcion, r, exc: _forzar_permiso(funcion, r, exc, str(ruta)))
    else:
        ruta.unlink()


def _forzar_permiso(funcion, ruta, exc, objetivo: str) -> None:
    """Algunas cachés (ej. módulos de Go) son de solo lectura: se les da permiso de escritura y se reintenta.

    Solo se tocan permisos de cosas DENTRO de lo que se está borrando: si falla la carpeta misma
    (ej. la carpeta madre no es tuya), el error sigue de largo.
    """
    padre = os.path.dirname(ruta)
    if not (padre == objetivo or padre.startswith(objetivo + "/")):
        raise exc
    os.chmod(padre, os.stat(padre).st_mode | stat.S_IWUSR)
    if os.path.isdir(ruta) and not os.path.islink(ruta):
        os.chmod(ruta, os.stat(ruta).st_mode | stat.S_IWUSR | stat.S_IXUSR)
    funcion(ruta)


def _a_papelera(ruta: Path) -> None:
    r = subprocess.run(["gio", "trash", "--", str(ruta)], capture_output=True, text=True)
    if r.returncode != 0:
        raise OSError(r.stderr.strip() or "gio trash falló")


def _comandos(tarea: Tarea, verif: Verificador, correr: Correr) -> Resultado:
    lim = tarea.hallazgo.limpieza
    assert lim
    for cmd in tarea.comandos:
        if cmd[0] == "rm":  # los rm también pasan por la verificación, ruta por ruta
            for arg in cmd[1:]:
                if not arg.startswith("-") and (motivo := verif.problema(arg)) and motivo != "ya no existe":
                    return Resultado(tarea, False, f"bloqueado por seguridad: {arg}: {motivo}")
    hechos = no_estaban = 0
    for cmd in tarea.comandos:
        cmd = _sin_lo_que_ya_no_existe(cmd)
        if cmd is None:
            no_estaban += 1
            continue
        completo = (["sudo"] if lim.sudo else []) + cmd
        codigo = correr(completo)
        if codigo != 0:
            return Resultado(tarea, False, f"«{' '.join(cmd[:3])}…» terminó con error ({codigo})")
        hechos += 1
    if no_estaban and not hechos:
        return Resultado(tarea, True, "ya no estaba (se borró antes)")
    return Resultado(tarea, True, "hecho" + (f" · {no_estaban} ya no estaban" if no_estaban else ""))


def _sin_lo_que_ya_no_existe(cmd: list[str]) -> list[str] | None:
    """Saca del comando lo que ya no existe. None = no queda nada que hacer.

    - rm: se sacan las rutas que ya no están (rm -r falla con rutas inexistentes).
    - timeshift --delete --snapshot X: si la snapshot ya no está, no hay nada que borrar.
    """
    if cmd[0] == "rm":
        opciones = [a for a in cmd[1:] if a.startswith("-")]
        rutas = [a for a in cmd[1:] if not a.startswith("-") and os.path.lexists(a)]
        return ["rm", *opciones, *rutas] if rutas else None
    if cmd[0] == "timeshift" and "--delete" in cmd and "--snapshot" in cmd:
        nombre = cmd[cmd.index("--snapshot") + 1]
        return cmd if os.path.isdir(f"/timeshift/snapshots/{nombre}") else None
    return cmd


def _registrar(res: Resultado) -> Resultado:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(json.dumps({
                "fecha": datetime.now().isoformat(timespec="seconds"),
                "hallazgo": res.tarea.hallazgo.titulo,
                "modo": res.tarea.modo.value,
                "rutas": [str(r) for r in res.tarea.rutas],
                "comandos": res.tarea.comandos,
                "peso_estimado": res.tarea.peso,
                "ok": res.ok,
                "mensaje": res.mensaje,
                "errores": res.errores,
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return res
