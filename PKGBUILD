# Maintainer: luchomart <87014410+luchomart@users.noreply.github.com>
pkgname=archcleaner
pkgver=0.9.1
pkgrel=1
pkgdesc="Analizador y limpiador de disco para Arch Linux: qué ocupa espacio, qué es basura y desinstalaciones sin rastro (TUI)"
arch=('any')
url="https://github.com/luchomart/archcleaner"
license=('MIT')
depends=('python>=3.12' 'python-rich' 'python-textual' 'glib2' 'pacman')
optdepends=(
  'pacman-contrib: limpiar la caché de pacman con paccache'
  'timeshift: snapshot antes de desinstalar y limpieza de snapshots viejas (modo rsync)'
  'flatpak: desinstalar apps Flatpak y limpiar runtimes sin uso'
  'xdg-utils: abrir carpetas y desinstalar juegos de Steam'
  'xdg-user-dirs: reconocer tus carpetas personales en cualquier idioma'
)
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
  cd "$pkgname-$pkgver"
  install -d "$pkgdir/usr/lib/$pkgname"
  cp -r archcleaner "$pkgdir/usr/lib/$pkgname/"
  install -Dm644 archcleaner.py "$pkgdir/usr/lib/$pkgname/archcleaner.py"
  python -m compileall -q -d "/usr/lib/$pkgname" "$pkgdir/usr/lib/$pkgname"

  install -d "$pkgdir/usr/bin"
  printf '#!/bin/sh\nexec python /usr/lib/%s/archcleaner.py "$@"\n' "$pkgname" > "$pkgdir/usr/bin/$pkgname"
  chmod 755 "$pkgdir/usr/bin/$pkgname"

  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
  install -Dm644 README.md README.en.md -t "$pkgdir/usr/share/doc/$pkgname/"
}
