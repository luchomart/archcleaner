"""Sistema: logs de journald, coredumps, módulos de kernels viejos y snapshots de Timeshift."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

from .. import timeshift
from ..contexto import Contexto
from ..modelo import Hallazgo, Item, Limpieza, Modo, Nivel, items_ordenados
from ..util import ejecutar, humano, parsear_tamano
from ..i18n import tr

JOURNAL_OBJETIVO = 200 * 1024**2  # tamaño al que se recortarían los logs
DIAS_SNAPSHOT_VIEJA = 30


def detectar(ctx: Contexto) -> list[Hallazgo]:
    return [h for h in (_journal(), _coredumps(ctx), *_modulos_viejos(ctx), _timeshift(ctx),
                        _timeshift_viejas()) if h]


def _timeshift_viejas() -> Hallazgo | None:
    """Snapshots de más de 30 días. La más reciente nunca se ofrece, aunque sea vieja."""
    if not timeshift.disponible():
        return None
    snaps = timeshift.listar()
    viejas = [s for s in snaps[:-1] if s.dias > DIAS_SNAPSHOT_VIEJA]
    if not viejas:
        return None
    detalle, incompleto = [], False
    for s in viejas:
        peso, inc = timeshift.peso_exclusivo(s)
        incompleto |= inc
        nota = f" · {s.comentario}" if s.comentario else ""
        detalle.append(Item(tr("{nombre}  ({tipo}, hace {dias} días{nota})", nombre=s.nombre, tipo=s.tipo,
                              dias=s.dias, nota=nota), peso,
                            comando=timeshift.comando_borrar(s)))
    return Hallazgo(
        tr("Sistema"), tr("Snapshots de Timeshift de más de {n} días", n=DIAS_SNAPSHOT_VIEJA), Nivel.REVISAR,
        sum(i.peso or 0 for i in detalle),
        tr("Las snapshots manuales Timeshift no las borra nunca solo, así que se acumulan. "
          "El peso es lo que se libera de verdad: solo los archivos que no comparte con otras snapshots. "
          "La más reciente ({nombre}) se conserva siempre.", nombre=snaps[-1].nombre),
        detalle=items_ordenados(detalle), incompleto=incompleto,
        limpieza=Limpieza(Modo.COMANDO, sudo=True, por_item=True,
                          texto=tr("timeshift --delete de las snapshots elegidas")),
    )


def _journal() -> Hallazgo | None:
    sal = ejecutar(["journalctl", "--disk-usage"])
    usado = parsear_tamano(sal or "")
    if not usado or usado <= JOURNAL_OBJETIVO * 1.5:
        return None
    return Hallazgo(
        tr("Sistema"), tr("Logs viejos del sistema (journald)"), Nivel.SEGURO,
        usado - JOURNAL_OBJETIVO,
        tr("Los registros del sistema ocupan {usado}. Se recortan a los {objetivo} más recientes: "
          "alcanza de sobra para diagnosticar problemas.", usado=humano(usado), objetivo=humano(JOURNAL_OBJETIVO)),
        rutas=[Path("/var/log/journal")],
        limpieza=Limpieza(Modo.COMANDO, [["journalctl", f"--vacuum-size={JOURNAL_OBJETIVO // 1024**2}M"]], sudo=True),
    )


def _coredumps(ctx: Contexto) -> Hallazgo | None:
    carpeta = Path("/var/lib/systemd/coredump")
    try:
        archivos = [e for e in os.scandir(carpeta) if e.is_file(follow_symlinks=False)]
    except OSError:
        return None
    if not archivos:
        return None
    por_programa: dict[str, list[int]] = defaultdict(list)
    rutas = [Path(e.path) for e in archivos]
    for e in archivos:
        partes = e.name.split(".")
        programa = partes[1] if len(partes) > 2 else e.name
        por_programa[programa].append(e.stat(follow_symlinks=False).st_blocks * 512)
    total = sum(sum(v) for v in por_programa.values())
    ctx.reclamar(carpeta)
    detalle = items_ordenados([Item(tr("{programa} ({n} cuelgues)", programa=prog, n=len(v)), sum(v))
                               for prog, v in por_programa.items()])
    return Hallazgo(
        tr("Sistema"), tr("Coredumps (programas que se colgaron)"), Nivel.SEGURO, total,
        tr("Cuando un programa se cuelga, systemd guarda una 'foto' de su memoria para depurarlo. "
          "Hay {n}. No sirven para nada salvo que estés reportando un bug. "
          "Si un programa aparece muchas veces, es una pista de que algo anda mal con él.", n=len(archivos)),
        rutas=[carpeta], detalle=detalle,
        limpieza=Limpieza(Modo.COMANDO, [["rm", "-f", "--", *map(str, rutas)]], sudo=True,
                          texto=tr("rm de los {n} coredumps en {carpeta}", n=len(rutas), carpeta=carpeta)),
    )


def _modulos_viejos(ctx: Contexto) -> list[Hallazgo]:
    """Carpetas en /usr/lib/modules que ya no pertenecen a ningún kernel instalado."""
    base = Path("/usr/lib/modules")
    res = []
    try:
        versiones = [d for d in base.iterdir() if d.is_dir()]
    except OSError:
        return res
    actual = os.uname().release
    for d in versiones:
        if d.name == actual:
            continue
        if ejecutar(["pacman", "-Qoq", str(d)]):
            continue  # pertenece a un kernel instalado (ej. linux-lts)
        peso, inc = ctx.medir(d)
        res.append(Hallazgo(
            tr("Sistema"), tr("Módulos de un kernel que ya no está ({version})", version=d.name), Nivel.REVISAR, peso,
            tr("Quedaron de un kernel desinstalado o actualizado (a veces los deja DKMS). "
              "No es el kernel que estás usando ahora."),
            rutas=[d], limpieza=Limpieza(Modo.COMANDO, [["rm", "-r", "--", str(d)]], sudo=True), incompleto=inc,
        ))
    return res


def _timeshift(ctx: Contexto) -> Hallazgo | None:
    try:
        conf = json.loads(Path("/etc/timeshift/timeshift.json").read_text())
    except (OSError, ValueError):
        return None
    if conf.get("btrfs_mode") == "true":
        return None
    raiz_snap = Path("/timeshift/snapshots")
    try:
        snaps = sorted(d.name for d in raiz_snap.iterdir() if d.is_dir())
    except OSError:
        snaps = []

    uuid_backup = conf.get("backup_device_uuid", "")
    uuid_raiz = (ejecutar(["findmnt", "-no", "UUID", "/"]) or "").strip()
    mismo_disco = bool(uuid_backup) and uuid_backup == uuid_raiz

    if snaps:
        peso, inc = ctx.medir(raiz_snap)
        texto = tr("Hay {n} snapshot(s): {nombres}.", n=len(snaps), nombres=", ".join(snaps[-5:]))
    else:
        peso, inc = 0, False
        texto = tr("Ahora mismo no hay snapshots guardadas.")
    estimado = int(conf.get("snapshot_size") or 0)
    if estimado:
        texto += tr(" Cada snapshot nueva ocupa unos {peso} (las siguientes, solo lo que cambió).",
                   peso=humano(estimado))
    if mismo_disco:
        texto += tr(" OJO: se guardan en el MISMO disco del sistema. Si ese disco falla, "
                   "perdés el sistema y las snapshots juntos.")
    texto += tr(" Esto se maneja desde Timeshift, no desde acá.")
    ctx.reclamar("/timeshift")
    return Hallazgo(
        tr("Sistema"), tr("Snapshots de Timeshift"), Nivel.INFO, peso, texto,
        rutas=[Path("/timeshift")], incompleto=inc, suma=False,
    )
