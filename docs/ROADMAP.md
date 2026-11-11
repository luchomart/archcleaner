# Hoja de ruta — ArchCleaner

## 📍 Dónde quedamos (actualizado 2026-11-11)
- **v0.11.0 lista pero sin publicar: Luciano la está probando** con sus datos reales.
  Novedades: 🤖 «¿Qué es esto?» (IA local opcional, `ia.py` + `tui/que_es.py`, en Explorar y en la lista
  para limpiar; si duda, 🔎 Buscar en internet), 🙈 «No mostrar más» (`ignorados.py` + `tui/ocultos.py`,
  por ruta, guardado en estado.json) y clic que elige sin tildar ([ ] o espacio tilda).
  Después (2026-11-11): en Desinstalar, semáforo 🟢🟡🔴 por programa (`ficha.semaforo`, con el motivo abajo)
  y 🤖 «¿Qué es?» de programas (prompt propio; Steam excluido); los restos le dicen a la IA de qué programa son. 113 tests.
- **Próximo paso:** juntar lo que no convenza al usarlo (con capturas). Cuando diga "publicá la 0.11":
  regenerar capturas (`python docs/generar_capturas.py`, que muestren 🤖 y 🙈) → pasos de "Publicar una versión".
- Pendiente fuera de este repo: anotar en `ias-locales` (Decisiones, tarea 11) el prompt nuevo de "known"
  y el de programas (validado con un script suelto; convendría sumarlo como `pruebas/que_es_programa.py`).
- v0.10.1 publicada en GitHub. **Bloqueado: subir al AUR** (registro de cuentas cerrado por bots). Pasos abajo.

---

## Hecho
| Versión | Qué |
|---|---|
| fase 1 | Analizar qué ocupa el disco |
| fase 2 | Limpiar (con borrado definitivo confirmado) |
| 0.2.0 | Menú de inicio |
| 0.3.0 | Desinstalar sin dejar rastro (fase 3) |
| 0.4.0 | App textual única, todo clickeable (fase 4). 0.4.1: botón Actualizar (F5 / r) |
| 0.5.0 | Explorar carpetas |
| 0.6.0 | Juegos fuera de Steam agrupados por carpeta; Workshop con nombres reales. 0.6.1: tests de la interfaz |
| 0.7.0 | Barra de progreso del análisis |
| 0.8.0 | Desinstalar: ordenar por tamaño, menos usados, nombre o recién instalados |
| 0.9.0 | Historial y "Qué creció" (fase 5). 0.9.1: repaso general de seguridad y colores |
| 0.10.0 | Interfaz en español e inglés |
| 0.10.1 | Repaso de seguridad antes de hacerlo público (puntos de montaje, archivos de paquetes) |
| 0.11.0 (sin publicar) | 🤖 «¿Qué es esto?» (IA local opcional que solo explica) y 🙈 «No mostrar más» |

## Pendientes
- **AUR** (cuando reabra el registro). El nombre `archcleaner` está libre y el `PKGBUILD` ya está listo.
  1. El autor crea la cuenta (usuario sugerido: luchomart), tilda "Hide Email" y pega su clave SSH pública
     **sin el comentario final** (ahí está su email).
  2. `git clone ssh://aur@aur.archlinux.org/archcleaner.git`, copiar el `PKGBUILD`, `makepkg --printsrcinfo > .SRCINFO`.
  3. Commit con el email noreply y push. Antes de aceptar la huella SSH del servidor, consultarle.
- **Botones laterales del mouse** (pospuesto): no llegan desde Konsole. El soporte ya está
  (`tui/mouse_lateral.py` + Alt+←/→); faltaría remapearlos en Plasma o probar otra terminal.
