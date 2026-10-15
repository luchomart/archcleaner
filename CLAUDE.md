# ArchCleaner

Analizador y limpiador de disco para Arch Linux, en terminal (Python + rich/textual). Firma visible:
"ArchCleaner by luchomart". Repo **público**: https://github.com/luchomart/archcleaner (MIT).

**Antes de trabajar, leé `docs/ROADMAP.md` ("Dónde quedamos" arriba).** Decisiones y lecciones: `docs/PROYECTO.md`.
Estructura del código y cómo sumar un detector: sección "Para desarrolladores" del `README.md`.

## Comandos
- Tests: `python -m unittest discover -s tests -v` (home falso; **correr la suite completa tras cada cambio**).
- Linters: ruff + mypy en un venv (no están instalados en el sistema; `.venv/` está en `.gitignore`).
- Capturas: `python docs/generar_capturas.py` (es + en, siempre con datos inventados). Logo: `python docs/generar_logo.py`.
- Probar la app real: comando `archcleaner` (symlink en `~/.local/bin` al `archcleaner.py` del repo; sin argumentos abre el menú).
- Desinstalar de prueba: `tests/paquete-prueba/` arma un paquete falso, reinstalable.

## Publicar una versión
1. Subir `__version__` en `archcleaner/__init__.py` y `pkgver` en `PKGBUILD`.
2. Commit, `git tag vX.Y.Z`, push con tags, `gh release create vX.Y.Z`.
3. Recalcular el sha256 del tarball **público** del tag y actualizar `sha256sums` en el `PKGBUILD` (commit aparte).

## Reglas
- Seguridad primero: el análisis es de solo lectura; nada se borra sin confirmar. `acciones.py` es el único
  módulo que borra y `seguridad.py` es la última barrera. Ante la duda, 🟡 "revisalo" y no 🟢.
- **En pruebas nunca vaciar la papelera real ni usar `gio trash --empty`**: borrar solo archivos de prueba propios.
- Textos visibles en español dentro de `tr("…")` (no `t`: muchas funciones usan `t` como variable local);
  traducción en `archcleaner/idiomas/en.py`. `tests/test_i18n.py` exige que estén todas y con los mismos `{datos}`.
- Repo público: commits con el email noreply (ya configurado en el repo). Nada personal en capturas, tests ni docs.
- Comandos con sudo/pacman: la app se suspende y se contestan en la terminal. Borrado definitivo: escribir "borrar"
  en un modal. Estas dos cosas son decisiones del autor: no cambiarlas.
