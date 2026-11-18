#!/usr/bin/env bash
# Sestaví balíček dist/vaultquick-desktop_<verze>_all.deb.
#   packaging/build-deb.sh [verze]      (výchozí verze: poslední tag vX.Y.Z bez „v“)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-$(git -C "$REPO" describe --tags --abbrev=0 2>/dev/null | sed 's/^v//')}"
[ -n "$VERSION" ] || { echo "Zadejte verzi: packaging/build-deb.sh 1.0.0" >&2; exit 2; }

PKG=vaultquick-desktop
SHARE=/usr/share/$PKG
OUT="$REPO/dist"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
chmod 755 "$ROOT"

# Pomocník vqd
(cd "$REPO" && ./gradlew -q :vqd:installDist && ./gradlew -q --stop)
install -d "$ROOT$SHARE/vqd"
cp -a "$REPO/vqd/build/install/vqd/." "$ROOT$SHARE/vqd/"

# Applet (bez testů a cache)
install -d "$ROOT$SHARE/applet"
cp -a "$REPO/applet/vqapplet" "$ROOT$SHARE/applet/"
install -m755 "$REPO/applet/vaultquick-applet" "$ROOT$SHARE/applet/"
find "$ROOT$SHARE" -name __pycache__ -type d -prune -exec rm -rf {} +
rm -f "$ROOT$SHARE/vqd/bin/vqd.bat"

# Soubor appletu pro panel a D-Bus služba (s cestou k appletu)
render() { sed "s#@APPLET_DIR@#$SHARE/applet#g" "$1" | install -D -m644 /dev/stdin "$2"; }
render "$REPO/applet/org.mate.panel.applet.VaultQuickTasks.mate-panel-applet.in" \
  "$ROOT/usr/share/mate-panel/applets/org.mate.panel.applet.VaultQuickTasks.mate-panel-applet"
render "$REPO/applet/org.mate.panel.applet.VaultQuickTasksFactory.service.in" \
  "$ROOT/usr/share/dbus-1/services/org.mate.panel.applet.VaultQuickTasksFactory.service"

# Příkaz pro klávesovou zkratku
install -D -m755 "$REPO/applet/vaultquick-desktop" "$ROOT/usr/bin/vaultquick-desktop"

# Dokumentace a licence
install -D -m644 "$REPO/LICENSE" "$ROOT/usr/share/doc/$PKG/copyright"
install -D -m644 "$REPO/README.md" "$ROOT/usr/share/doc/$PKG/README.md"
install -D -m644 "$REPO/README.cs.md" "$ROOT/usr/share/doc/$PKG/README.cs.md"

chmod -R u+rwX,go+rX,go-w "$ROOT/usr"

SIZE="$(du -sk "$ROOT/usr" | cut -f1)"
install -d "$ROOT/DEBIAN"
cat > "$ROOT/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Architecture: all
Maintainer: PeSstudios <355266694+PeSstudios@users.noreply.github.com>
Installed-Size: $SIZE
Depends: mate-panel, python3, python3-gi, gir1.2-gtk-3.0, gir1.2-matepanelapplet-4.0, libglib2.0-bin, default-jre-headless (>= 2:1.17) | java17-runtime-headless
Section: gnome
Priority: optional
Homepage: https://github.com/PeSstudios/VaultQuickDesktop
Description: Obsidian (TaskNotes) tasks on the MATE panel
 MATE panel applet: counts of today's and overdue tasks on the panel, a
 multi-day agenda on click, checking off and quickly adding tasks. Reads and
 writes TaskNotes tasks directly in your Obsidian vault.
EOF

mkdir -p "$OUT"
DEB="$OUT/${PKG}_${VERSION}_all.deb"
fakeroot dpkg-deb --build -Zxz "$ROOT" "$DEB" >/dev/null
echo "$DEB"
