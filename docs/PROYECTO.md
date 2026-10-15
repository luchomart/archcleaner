# ArchCleaner: visión, decisiones y lecciones

## Qué es y por qué existe
Una herramienta para ver **qué ocupa el disco** en Arch Linux, separar lo que es basura segura de lo que
"pesa mucho pero conviene revisar", y **desinstalar programas sin dejar rastros**. Nació de la experiencia
en Windows de ir carpeta por carpeta buscando al culpable.

Alcance: todo el sistema, incluidos Steam, Flatpak, AUR y discos extra montados en `/mnt`.

## Decisiones

| Tema | Decisión |
|---|---|
| Interfaz | Terminal bonita (rich + textual), sin GUI. Una sola app donde todo se puede clickear. |
| Comando | `archcleaner` sin argumentos abre el menú; también hay subcomandos (`analizar`, `limpiar --simulacro`, `desinstalar`, `explorar`, `crecio --dias N`) con alias en inglés. |
| Datos propios | Estado, log, informes e historial en `~/.local/state/archcleaner/`. ArchCleaner nunca propone borrar sus propios datos. |
| Colores | 🟢 seguro (tildado por defecto) · 🟡 revisalo (sin tildar). La papelera y las cachés caras de regenerar (huggingface, torch, playwright, JetBrains...) son 🟡. |
| Borrado definitivo | Permitido, pero hay que escribir "borrar" en un modal (en inglés, "delete"). |
| sudo y pacman | La app se suspende (`App.suspend`) y se contestan en la terminal, a la vista. |
| Timeshift | Antes de desinstalar se pregunta si sacar una snapshot (por defecto no; sí si son más de 15 paquetes). Limpiar ofrece borrar snapshots de más de 30 días, nunca la más reciente. |
| Explorar | Solo borra dentro de home y `/mnt`; el resto del sistema es de solo lectura. |
| Último uso de un programa | atime de sus ejecutables (ignorando el horario de las snapshots de Timeshift, porque rsync cambia el atime), `LastPlayed` de Steam y `~/.var/app` para Flatpak. |
| Historial | Una foto comprimida por análisis completo (carpetas ≥ 1 MB y espacio libre por disco). Se poda: todo 7 días, semanal hasta 90, después mensual. |
| Idiomas | Español e inglés. Idioma por `LANG`, `--lang` o `ARCHCLEANER_LANG`; la CLI lo fija antes de importar porque hay textos armados al importar. |
| Progreso | La barra reparte el avance según los tiempos guardados de análisis anteriores (por raíz y por detector). |
| Distribución | GitHub (releases) + `PKGBUILD` en la raíz, que baja el tarball del tag. Objetivo: AUR. |
| CI | GitHub Actions en un contenedor de Arch, tests como usuario sin privilegios. |

## Seguridad del borrado (`seguridad.py`)
- Rechaza carpetas con un punto de montaje adentro (lee `/proc/self/mountinfo` cada vez).
- En zonas del sistema rechaza todo lo que pertenezca a un paquete (`pacman -Qo`), por ejemplo módulos de kernels instalados.
- Si hay un enlace simbólico en el camino, verifica la ruta real.
- Los restos en `/etc` y `/var/lib` se bloquean si adentro hay archivos de paquetes.
- Los `rm -r` llevan `--one-file-system`. Nunca toca permisos fuera de lo que va a borrar.
- Los huérfanos excluyen los paquetes protegidos.

## Lecciones técnicas
- Las carpetas de `compatdata`/`shadercache` con ID ≥ 2³¹ son de **juegos no-Steam** agregados a Steam: no son restos.
- Los juegos de Steam y las AppImages del PATH cuentan como "instalados", para no marcar sus carpetas de datos
  como restos (por ejemplo, Terraria guarda partidas en `~/.local/share/Terraria`).
- Las carpetas con partidas guardadas (saves, worlds, `~/.minecraft`) nunca son "seguras".
- La caché de pacman guarda `.pkg.tar.zst` **y** `.sig`: hay que borrar los dos.
- Juegos fuera de Steam: se agrupan subiendo desde el archivo gigante hasta la carpeta que tiene el `.exe` o los
  archivos de Unreal/Unity.
- Si se desinstala un programa de DNS (nextdns u otro), revisar `/etc/resolv.conf`.
- Con la caché caliente el análisis tarda unos segundos; en frío, bastante más.
