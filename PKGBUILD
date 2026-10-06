# Maintainer: luchomart <87014410+luchomart@users.noreply.github.com>
pkgname=archcleaner
pkgver=0.10.1
pkgrel=1
pkgdesc="Disk analyzer, junk cleaner and trace-free uninstaller for Arch Linux (TUI, English/Spanish)"
arch=('any')
url="https://github.com/luchomart/archcleaner"
license=('MIT')
depends=('python>=3.12' 'python-rich' 'python-textual' 'glib2' 'pacman')
optdepends=(
  'pacman-contrib: clean the pacman cache with paccache'
  'timeshift: snapshot before uninstalling and cleanup of old snapshots (rsync mode)'
  'flatpak: uninstall Flatpak apps and clean unused runtimes'
  'xdg-utils: open folders and uninstall Steam games'
  'xdg-user-dirs: recognize your personal folders in any language'
)
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('ac683dae44fc4fff547f5e3b9d1cb9d2198d0463392bde594fc4decaccb67b18')

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
