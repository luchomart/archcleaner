# 🧹 ArchCleaner

[![tests](https://github.com/luchomart/archcleaner/actions/workflows/tests.yml/badge.svg)](https://github.com/luchomart/archcleaner/actions/workflows/tests.yml)
[![licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)
![Arch Linux](https://img.shields.io/badge/Arch_Linux-1793D1?logo=arch-linux&logoColor=white)

**🇬🇧 [Read in English](README.en.md)**

Analizador y limpiador de disco para Arch Linux, en la terminal y con mouse. Te dice **qué ocupa
espacio, por qué, y qué se puede borrar**, y desinstala programas **sin dejar rastro**.

![Menú de ArchCleaner](docs/capturas/menu.svg)

Se acabó ir carpeta por carpeta buscando al culpable: ArchCleaner recorre tus discos, reconoce
la basura conocida (cachés, logs, paquetes viejos, restos de Steam, `node_modules` olvidados…) y
la separa en tres niveles:

| Nivel | Qué significa | ¿Viene tildado? |
|---|---|---|
| 🟢 Basura segura | Se regenera sola; borrarla no rompe nada | Sí |
| 🟡 Para revisar | Pesa y probablemente sobra, pero decidís vos | No |
| 🔵 Solo informativo | Pesa, pero no se toca desde acá (juegos de Steam, Timeshift…) | — |

## 🛡️ ¿Es seguro?

Un programa que borra cosas tiene que ganarse la confianza. Así trabaja ArchCleaner:

- **Analizar no borra nada.** Nunca. Podés usarlo solo para mirar.
- **Nada se borra sin que lo veas antes:** siempre hay un plan con la lista exacta, y un modo
  **simulacro** que muestra todo sin ejecutar nada.
- **Lo dudoso va a la papelera**, de donde lo podés recuperar. Borrar para siempre es opcional y
  pide **escribir `borrar`** para confirmar.
- **No corre como root.** Pide `sudo` solo para el paso puntual que lo necesita, y la contraseña
  la escribís vos en la terminal. Las desinstalaciones las hace **pacman**, con su propia confirmación.
- **Una última barrera revisa cada ruta** antes de borrarla ([`seguridad.py`](archcleaner/seguridad.py)):
  nunca toca el sistema, tu home, tus carpetas personales (Documentos, Imágenes…), discos enteros
  ni archivos que pertenezcan a un paquete instalado, aunque algo lo pida por error. Los enlaces
  simbólicos se borran como enlaces, nunca lo que hay del otro lado.
- **Los paquetes vitales están protegidos** (kernel, systemd, pacman, escritorio, drivers,
  bootloader…): aparecen con 🔒 y no se pueden desinstalar desde acá.
- **Lo que tiene pinta de partidas guardadas** (`saves`, `worlds`…) nunca viene tildado.
- **Puede crear una snapshot de Timeshift** antes de desinstalar, para volver atrás si algo sale mal.
- **Todo queda anotado** en `~/.local/state/archcleaner/acciones.log`.
- **Código abierto y con tests:** 64 tests automáticos (las reglas de seguridad, y la app manejada
  con clics en un home falso) corren en cada cambio.

## 📸 Capturas

| Análisis | Elegir qué limpiar |
|---|---|
| ![Análisis](docs/capturas/analisis.svg) | ![Limpiar](docs/capturas/limpiar.svg) |
| **Borrado definitivo: hay que escribir «borrar»** | **Desinstalar: ordenar por menos usados** |
| ![Confirmar borrado](docs/capturas/confirmar-borrado.svg) | ![Desinstalar](docs/capturas/desinstalar.svg) |
| **Qué creció desde la semana pasada** | **Explorar carpetas por peso** |
| ![Qué creció](docs/capturas/que-crecio.svg) | ![Explorar](docs/capturas/explorar.svg) |

> Las capturas son de una PC de demostración ([`docs/generar_capturas.py`](docs/generar_capturas.py)).

## 📦 Instalación

**Con el PKGBUILD** (recomendado: queda instalado como paquete y se desinstala limpio con pacman):

```bash
git clone https://github.com/luchomart/archcleaner.git
cd archcleaner
makepkg -si
```

**Sin instalar nada** (para probarlo):

```bash
sudo pacman -S --needed python-rich python-textual
git clone https://github.com/luchomart/archcleaner.git
python archcleaner/archcleaner.py
```

Opcionales: `pacman-contrib` (limpiar la caché de pacman), `timeshift` (snapshots), `flatpak`.

**Desinstalar:** `sudo pacman -R archcleaner`. Sus datos (log, historial, preferencias) están en
`~/.local/state/archcleaner/`: borrá esa carpeta si no los querés.

**Requisitos:** Arch Linux (o derivadas con pacman), Python ≥ 3.12 y una terminal moderna con mouse
(Konsole, Kitty, Alacritty, GNOME Terminal, WezTerm…). La interfaz está en español.

## 🚀 Uso

```bash
archcleaner                      # la app: menú con todo (teclado o mouse)
archcleaner analizar             # informe completo en la terminal (solo lectura)
archcleaner analizar --rapido    # solo fuentes de basura conocidas, sin recorrer los discos
archcleaner limpiar --simulacro  # elegís qué limpiar y ves el plan, sin borrar nada
archcleaner limpiar              # lo mismo, pero al final pregunta y ejecuta
archcleaner desinstalar          # elegís un programa de la lista
archcleaner desinstalar steam    # directo a ese programa
archcleaner explorar ~/Descargas # navegar carpetas ordenadas por peso
archcleaner crecio --dias 7      # qué creció desde hace una semana
```

Todo es clickeable. **🔄 Actualizar** (`F5`) vuelve a buscar en cualquier pantalla, y
**Alt+← / Alt+→** (o los botones laterales del mouse, si tu terminal los manda) van atrás y adelante.

### 📦 Desinstalar sin dejar rastro

1. **Ficha** (solo lectura): qué paquetes se van (incluidas las dependencias que quedan sin uso),
   servicios activos, y restos en tu home y en el sistema que pacman no conoce.
2. **Elegís los restos:** los *seguros* (nombre exacto) vienen tildados; los *probables* no.
3. **Plan → papelera o definitivo → snapshot de Timeshift (opcional) → confirmar.**
4. Apaga servicios → desinstala → borra restos → **verifica**: «Rastro: 0», o qué quedó y por qué.

Funciona con repos y AUR (`pacman -Rns`), Flatpak, AppImage y juegos de Steam (ArchCleaner se da
cuenta solo cuando Steam terminó de desinstalar, y después limpia shaders, Workshop y Proton).
La lista se puede ordenar por **tamaño, menos usados, nombre o recién instalados**.

### 📈 Qué creció

Cada análisis guarda una foto liviana del disco (~20-100 KB). Después podés comparar con el análisis
anterior, con hace una semana o un mes: te muestra un árbol que apunta a la carpeta culpable
(`~/.local/share/Steam/steamapps/workshop +5 GB`, no solo `~/.local +5 GB`). También aparece en el
informe, en Explorar (▲/▼ al lado de cada carpeta) y como mini gráfica del espacio libre en el menú.

### 📂 Explorar

Carpetas y archivos de lo más pesado a lo más liviano, con lo que ArchCleaner sabe de cada uno
(«🟢 caché», «juego: …», «workshop: …»). Podés mandar a la papelera o borrar, siempre pasando por la
barrera de seguridad; fuera de tu home y de tus discos de datos es solo para mirar.

## 🔍 Qué revisa

- **Sistema:** logs de journald, coredumps, módulos de kernels viejos, snapshots de Timeshift de más
  de 30 días (nunca la más reciente).
- **Pacman / AUR:** caché de paquetes, huérfanos, `.pacnew`/`.pacsave`, caché de yay/paru, paquetes `-debug`.
- **Flatpak:** runtimes sin uso, datos de apps desinstaladas.
- **Steam (todas las bibliotecas):** shaders, Proton y Workshop de juegos desinstalados, descargas a
  medias, versiones de Proton sin uso, el peso de cada juego y del Workshop (con el nombre de cada ítem).
- **Desarrollo:** cachés de npm/pip/go/cargo/gradle/maven…, `node_modules` y `venv` olvidados.
- **Home:** `~/.cache`, papelera, descargas viejas, restos de programas que ya no están.
- **Archivos:** archivos de más de 1 GB, instaladores ya usados y juegos instalados por fuera de Steam.
- **Árbol del peso:** dónde está el espacio, carpeta por carpeta, en cada disco.

## 🛠️ Para desarrolladores

```bash
python -m unittest discover -s tests     # los tests (no tocan tus archivos: usan un home falso)
python docs/generar_capturas.py          # regenera las capturas del README
```

```
archcleaner/
  cli.py          comandos                  acciones.py    el único módulo que borra
  analisis.py     escaneo + detectores      seguridad.py   la última barrera antes de borrar
  escaner.py      mide carpetas (como du)   ficha.py       investiga un programa (paquetes, restos)
  historial.py    fotos y «qué creció»      programas.py   programas instalados y su último uso
  detectores/     un archivo por fuente de basura
  tui/            la app (textual): una pantalla por paso
```

Para sumar una fuente de basura nueva: crear `detectores/<nombre>.py` con
`detectar(ctx) -> list[Hallazgo]` y agregarlo a `DETECTORES` en `detectores/__init__.py`.

¿Encontraste un error o algo que debería detectar? Abrí un [issue](https://github.com/luchomart/archcleaner/issues).

## Licencia

[MIT](LICENSE) © luchomart
