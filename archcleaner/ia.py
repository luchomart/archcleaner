"""🤖 "¿Qué es esto?": una IA local (Ollama) explica qué es una carpeta o archivo. Opcional y de solo lectura.

La IA solo EXPLICA: no cambia ninguna marca 🟢/🟡 ni decide qué se borra. Se le manda la ruta, el
tamaño, el paquete dueño y lo más pesado de adentro; nunca el contenido de los archivos, y todo
queda en la PC (Ollama corre en localhost).

El modelo no redacta la respuesta: llena un JSON con un esquema fijo y las frases las pone la app
(traducidas con tr). Así "no estoy seguro" es un campo (`known`) y no algo que el modelo tenga que
acordarse de escribir. Prompt, esquema y modelo salen de una comparación con 15 carpetas reales e
inventadas (qwen3.5:9b: reconoció 23/24 reales y dudó en 6/6 inventadas). "known" no pide conocer la
ruta exacta sino el tipo de cosa: con la versión estricta dudaba hasta con node_modules y .venv.

Modelo: ARCHCLEANER_MODELO (por defecto qwen3.5:9b). Servidor: OLLAMA_HOST (por defecto 127.0.0.1:11434).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .i18n import tr

MODELO_POR_DEFECTO = "qwen3.5:9b"
MAX_ADENTRO = 20  # cuántas cosas de adentro se le pasan al modelo
EFECTOS = ("rebuilt", "settings", "data", "package")

SISTEMA = """You explain to a Linux user what a folder or file on their disk is. You get its path, size, the package that owns it (if any) and the largest items inside. You never see file contents.

Reply with JSON:
- "known": true if you recognize what this is: a well-known program, tool or standard kind of folder (for example node_modules, .venv, __pycache__, build caches, KDE caches), even if the exact path is new to you. A name you have never heard of is not knowledge: an unfamiliar name means false.
- "what": one short sentence saying what it is. If "known" is false, do not name or describe any program: only say what the contents look like (for example "large data files with an index, maybe a database").
- "program": the program that uses it, or "" if "known" is false.
- "if_deleted": one of
  "rebuilt" (caches, thumbnails, search indexes, compiled shaders, downloaded packages: rebuilt or downloaded again by itself),
  "settings" (configuration, logins, preferences),
  "data" (documents, game saves, browser profiles, mail, virtual machines, containers, Wine or Proton prefixes, trash),
  "package" (installed program files owned by a package, for example in /usr or /opt).
  Wine and Proton prefixes can hold game saves, and Docker keeps volumes: they are "data".
  If you hesitate between "rebuilt" and "data", choose "data". If "known" is false and there is no owning package, use "data".
- "detail": one short sentence about what exactly is lost or rebuilt. The app already writes "if deleted" before it: do not repeat it. Do not tell the user whether to delete it.

Write "what" and "detail" in {idioma}{trato}. Never invent program names, features, websites or commands."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "known": {"type": "boolean"},
        "what": {"type": "string"},
        "program": {"type": "string"},
        "if_deleted": {"type": "string", "enum": list(EFECTOS)},
        "detail": {"type": "string"},
    },
    "required": ["known", "what", "program", "if_deleted", "detail"],
}

# Cómo se le pide el idioma al modelo (es para el modelo, no para el usuario: no va con tr).
# En español, impersonal: pedirle voseo producía "necesitéis", "vuelvá".
IDIOMA_MODELO = {
    "es": ("Spanish", ' (impersonal, without addressing the user: "se pierden las partidas", not "perdés" or "pierdes")'),
    "en": ("English", ""),
}


def modelo() -> str:
    return os.environ.get("ARCHCLEANER_MODELO", "").strip() or MODELO_POR_DEFECTO


def servidor() -> str:
    host = os.environ.get("OLLAMA_HOST", "").strip() or "127.0.0.1:11434"
    return host if host.startswith(("http://", "https://")) else f"http://{host}"


@dataclass
class Datos:
    """Lo que se le cuenta al modelo de una carpeta o archivo."""
    ruta: str
    carpeta: bool
    peso: str                                   # ya legible ("2.3 GB")
    paquetes: list[str] = field(default_factory=list)  # dueños según pacman ("pacman 7.1.0-1"); [] = ninguno
    adentro: list[tuple[str, str]] | None = None  # (nombre, peso legible), lo más pesado primero
    contexto: str = ""  # dónde lo listó ArchCleaner ("Dependencias de proyectos: …"), si se sabe


@dataclass
class Respuesta:
    conocido: bool
    que: str
    programa: str
    efecto: str      # uno de EFECTOS
    detalle: str


class SinIA(Exception):
    """Ollama no responde, falta el modelo o la respuesta no sirve. El mensaje es para el usuario."""


def _pedir(ruta: str, cuerpo: dict | None = None, timeout: float = 120) -> dict:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(servidor() + ruta, datos, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def disponible() -> bool:
    """¿Hay un Ollama respondiendo? (rápido: se usa para mostrar o no el botón)."""
    try:
        _pedir("/api/tags", timeout=1)
        return True
    except (OSError, ValueError):
        return False


def tiene_modelo() -> bool:
    try:
        nombres = {m.get("name", "") for m in _pedir("/api/tags", timeout=3).get("models", [])}
    except (OSError, ValueError):
        return False
    buscado = modelo()
    return buscado in nombres or f"{buscado}:latest" in nombres


def mensaje(d: Datos, idioma: str) -> str:
    """Los datos en un formato fijo, en inglés (es para el modelo)."""
    lineas = [
        f"Path: {d.ruta}",
        f"Type: {'folder' if d.carpeta else 'file'}",
        f"Size: {d.peso}",
        f"Owning package: {', '.join(d.paquetes[:5]) + (', …' if len(d.paquetes) > 5 else '') or 'none'}",
    ]
    if d.adentro:
        lineas.append("Largest items inside:")
        lineas += [f"- {nombre} ({peso})" for nombre, peso in d.adentro[:MAX_ADENTRO]]
    if d.contexto:
        lineas.append(f"ArchCleaner listed it under: {d.contexto}")
    lineas.append(f"\nAnswer in {IDIOMA_MODELO.get(idioma, IDIOMA_MODELO['en'])[0]}.")
    return "\n".join(lineas)


def _interpretar(crudo: str, d: Datos) -> Respuesta:
    """JSON del modelo -> Respuesta, sin confiar en él: ante la duda, del lado seguro."""
    try:
        j = json.loads(crudo)
        r = Respuesta(bool(j["known"]), str(j["what"]).strip(), str(j["program"]).strip(),
                      str(j["if_deleted"]), str(j["detail"]).strip())
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise SinIA(tr("La IA respondió algo que no se entiende.")) from e
    r.que, r.detalle = _mayuscula(r.que), _mayuscula(r.detalle)
    original = r.efecto
    if r.efecto not in EFECTOS:
        r.efecto = "data"
    if not r.conocido:
        r.programa = ""  # si no lo conoce, que no nombre programas
        if not d.paquetes and r.efecto in ("rebuilt", "package"):
            r.efecto = "data"  # no conoce la carpeta: no puede prometer que se regenera
    if r.efecto == "package" and not d.paquetes:
        r.efecto = "data"  # "es de un paquete" solo si pacman lo confirma
    if r.efecto != original:
        r.detalle = ""  # el detalle hablaba del efecto que dijo el modelo ("se vuelve a bajar"): ya no corresponde
    return r


def _mayuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def preguntar(d: Datos, idioma: str) -> Respuesta:
    """Le pregunta al modelo (tarda unos segundos; más la primera vez, mientras lo carga). Lanza SinIA."""
    return _interpretar(_chat(SISTEMA, ESQUEMA, mensaje(d, idioma), idioma), d)


def _chat(sistema: str, esquema: dict, mensaje_: str, idioma: str) -> str:
    """Manda el pedido a Ollama y devuelve el JSON crudo que escribió el modelo. Lanza SinIA."""
    nombre, trato = IDIOMA_MODELO.get(idioma, IDIOMA_MODELO["en"])
    cuerpo = {
        "model": modelo(),
        "stream": False,
        "think": False,  # respuesta corta, sin razonar en voz alta
        "messages": [
            {"role": "system", "content": sistema.format(idioma=nombre, trato=trato)},
            {"role": "user", "content": mensaje_},
        ],
        "format": esquema,
        "options": {"temperature": 0.2},  # explicar, no crear: poca variación
    }
    try:
        res = _pedir("/api/chat", cuerpo)
    except urllib.error.HTTPError as e:
        e.close()
        if e.code == 404:
            raise SinIA(tr("Falta el modelo {modelo}. Bajalo con: ollama pull {modelo}", modelo=modelo())) from e
        raise SinIA(tr("Ollama respondió con un error ({codigo}).", codigo=e.code)) from e
    except (OSError, ValueError) as e:
        raise SinIA(tr("No se pudo hablar con Ollama: {error}", error=e)) from e
    return res.get("message", {}).get("content", "")


def lineas(r: Respuesta, d: Datos) -> list[str]:
    """Lo que se le muestra al usuario: frases de la app + lo que redactó el modelo."""
    res = [r.que] if r.conocido else [tr("No estoy seguro de qué es."), r.que]
    if r.conocido and r.programa:
        res.append(tr("Lo usa: {programa}.", programa=r.programa))
    if d.paquetes and not r.conocido:
        nombres = [p.split()[0] for p in d.paquetes]
        res.append(tr("Lo instaló el paquete {paquete}.", paquete=nombres[0]) if len(nombres) == 1 else
                   tr("Lo instalaron {n} paquetes: {paquetes}.", n=len(nombres), paquetes=", ".join(nombres[:5])
                      + (", …" if len(nombres) > 5 else "")))
    efecto = {
        "rebuilt": tr("Si se borra, se regenera solo."),
        "settings": tr("Si se borra, perdés configuración."),
        "data": tr("Si se borra, perdés datos."),
        "package": tr("Es parte de un paquete: se quita desinstalándolo."),
    }[r.efecto]
    res.append(f"{efecto} {r.detalle}".strip())
    return [x for x in res if x]


# ── Programas (pantalla Desinstalar) ─────────────────────────────────────────
# Lo mismo pero de un programa instalado. La IA solo explica: lo que ArchCleaner deja o no desinstalar
# (🟢 🟡 🔴) sale de datos reales (pacman, grupos, protegidos), nunca de acá.

EFECTOS_PROGRAMA = ("app", "feature", "system")

SISTEMA_PROGRAMA = """You explain to a Linux user what an installed program or package is. You get its name, where it was installed from, its description, size, package groups and which other packages use it.

Reply with JSON:
- "known": true if you recognize this program or package, or the project it comes from. A name you have never heard of is not knowledge: an unfamiliar name means false, even if a description is given.
- "what": one or two short sentences saying what it is and what it is used for. If "known" is false, only rephrase the description you were given, adding nothing; if there is no description, say that it is not clear what it does.
- "if_removed": one of
  "app" (a program or game that the user opens by themselves: removing it only loses that program),
  "feature" (it adds something to other programs or to the desktop: plugins, drivers, codecs, fonts, themes, thumbnails, helper tools that other programs call),
  "system" (a core piece of the system or the desktop: without it the desktop, the network, sound, graphics or booting may stop working).
  If you hesitate, choose the more cautious one: "system" over "feature", "feature" over "app".
- "detail": one short sentence about what stops working without it. The app already writes "if removed" before it: do not repeat it. Do not tell the user whether to remove it.

Write "what" and "detail" in {idioma}{trato}. Never invent program names, features, websites or commands."""

ESQUEMA_PROGRAMA = {
    "type": "object",
    "properties": {
        "known": {"type": "boolean"},
        "what": {"type": "string"},
        "if_removed": {"type": "string", "enum": list(EFECTOS_PROGRAMA)},
        "detail": {"type": "string"},
    },
    "required": ["known", "what", "if_removed", "detail"],
}

ORIGEN_MODELO = {
    "repo": "Arch Linux official repositories (pacman)",
    "aur": "AUR (Arch User Repository)",
    "flatpak": "Flatpak",
    "appimage": "AppImage file",
    "steam": "Steam (game or tool)",  # hoy la pantalla no lo pregunta (ver programas.py)
}


@dataclass
class DatosPrograma:
    """Lo que se le cuenta al modelo de un programa instalado."""
    nombre: str
    id: str                      # paquete, id de Flatpak, archivo del AppImage o appid de Steam
    origen: str                  # clave de programas.ORIGENES
    peso: str                    # ya legible
    version: str = ""
    descripcion: str = ""
    grupos: list[str] = field(default_factory=list)
    requerido_por: list[str] = field(default_factory=list)
    opcional_para: list[str] = field(default_factory=list)
    uso: str = ""                # en inglés, para el modelo ("12 days ago", "not since it was installed")

    @property
    def busqueda(self) -> str:
        """Qué se busca en internet: el paquete o el nombre (nunca rutas personales)."""
        if self.origen in ("repo", "aur", "flatpak"):
            return self.id
        return self.nombre


def _lista(nombres: list[str], maximo: int = 8) -> str:
    return ", ".join(nombres[:maximo]) + (", …" if len(nombres) > maximo else "") or "none"


def mensaje_programa(d: DatosPrograma, idioma: str) -> str:
    """Los datos del programa en un formato fijo, en inglés (es para el modelo)."""
    lineas = [f"Name: {d.nombre}"]
    if d.id != d.nombre and d.origen != "appimage":
        lineas.append(f"Package: {d.id}")
    lineas += [
        f"Installed from: {ORIGEN_MODELO.get(d.origen, d.origen)}",
        f"Version: {d.version or 'unknown'}",
        f"Description: {d.descripcion or 'none'}",
        f"Size: {d.peso}",
    ]
    if d.origen in ("repo", "aur"):
        lineas += [f"Package groups: {_lista(d.grupos)}",
                   f"Required by: {_lista(d.requerido_por)}",
                   f"Optional for: {_lista(d.opcional_para)}"]
    if d.uso:
        lineas.append(f"Last used: {d.uso}")
    lineas.append(f"\nAnswer in {IDIOMA_MODELO.get(idioma, IDIOMA_MODELO['en'])[0]}.")
    return "\n".join(lineas)


def _interpretar_programa(crudo: str) -> Respuesta:
    """JSON del modelo -> Respuesta (programa = ""), del lado prudente si algo no cierra."""
    try:
        j = json.loads(crudo)
        r = Respuesta(bool(j["known"]), str(j["what"]).strip(), "", str(j["if_removed"]), str(j["detail"]).strip())
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise SinIA(tr("La IA respondió algo que no se entiende.")) from e
    r.que, r.detalle = _mayuscula(r.que), _mayuscula(r.detalle)
    if not r.conocido:
        r.efecto, r.detalle = "unknown", ""  # sin saber qué es, no puede decir qué deja de andar
    elif r.efecto not in EFECTOS_PROGRAMA:
        r.efecto, r.detalle = "system", ""  # el detalle hablaba de otro efecto
    return r


def preguntar_programa(d: DatosPrograma, idioma: str) -> Respuesta:
    """Como preguntar(), pero de un programa instalado. Lanza SinIA."""
    return _interpretar_programa(_chat(SISTEMA_PROGRAMA, ESQUEMA_PROGRAMA, mensaje_programa(d, idioma), idioma))


def lineas_programa(r: Respuesta) -> list[str]:
    res = [r.que] if r.conocido else [tr("No estoy seguro de qué es."), r.que]
    efecto = {
        "app": tr("Si lo desinstalás, perdés ese programa."),
        "feature": tr("Si lo desinstalás, otros programas o el escritorio pierden algo."),
        "system": tr("Es una pieza del sistema: sin ella pueden dejar de andar cosas importantes."),
        "unknown": tr("Sin saber qué es, no puedo decir qué deja de andar si lo desinstalás."),
    }[r.efecto]
    res.append(f"{efecto} {r.detalle}".strip())
    return [x for x in res if x]
