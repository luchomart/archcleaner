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
    nombre, trato = IDIOMA_MODELO.get(idioma, IDIOMA_MODELO["en"])
    cuerpo = {
        "model": modelo(),
        "stream": False,
        "think": False,  # respuesta corta, sin razonar en voz alta
        "messages": [
            {"role": "system", "content": SISTEMA.format(idioma=nombre, trato=trato)},
            {"role": "user", "content": mensaje(d, idioma)},
        ],
        "format": ESQUEMA,
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
    return _interpretar(res.get("message", {}).get("content", ""), d)


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
