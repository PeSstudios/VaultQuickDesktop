#!/usr/bin/env bash
# Instalace appletu Úkoly VaultQuick pro panel MATE (idempotentní).
#   install.sh [--shortcut '<Mod4>t'] [--skip-build] [--dry-run]
#   install.sh --uninstall [--dry-run]
# --dry-run jen vypíše, co by se udělalo (nic nespouští ani nezapisuje).
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SRC/../.." && pwd)"
SHARE="$HOME/.local/share/vaultquick-desktop"
APPLET_DST="$SHARE/applet"
VQD_DST="$SHARE/vqd"
SERVICE_DST="$HOME/.local/share/dbus-1/services/org.mate.panel.applet.VaultQuickTasksFactory.service"
BIN_DST="$HOME/.local/bin/vaultquick-desktop"
PANEL_DST="/usr/share/mate-panel/applets/org.mate.panel.applet.VaultQuickTasks.mate-panel-applet"
KEYS="/org/mate/desktop/keybindings"

SHORTCUT=""
SKIP_BUILD=0
DRY=0
UNINSTALL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --shortcut) SHORTCUT="${2:?--shortcut vyžaduje zkratku, např. '<Mod4>t'}"; shift 2 ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --dry-run) DRY=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help) sed -n 2,6p "$0"; exit 0 ;;
    *) echo "Neznámý argument: $1" >&2; exit 2 ;;
  esac
done

# Provede příkaz, nebo ho jen vypíše (--dry-run).
run() {
  if [ "$DRY" = 1 ]; then printf '[dry-run]'; printf ' %q' "$@"; printf '\n'; else "$@"; fi
}

# Zapíše do cíle obsah šablony s dosazenou cestou k appletu.
render() { # šablona cíl [sudo]
  local tpl="$1" dst="$2" use_sudo="${3:-}"
  if [ "$DRY" = 1 ]; then
    echo "[dry-run] dosadit @APPLET_DIR@=$APPLET_DST do $(basename "$tpl") → $dst${use_sudo:+ (sudo)}"
    return
  fi
  local tmp; tmp="$(mktemp)"
  sed "s#@APPLET_DIR@#$APPLET_DST#g" "$tpl" > "$tmp"
  if [ -n "$use_sudo" ]; then
    sudo install -m644 "$tmp" "$dst"
  else
    install -D -m644 "$tmp" "$dst"
  fi
  rm -f "$tmp"
}

# Seznam již použitých zkratek: "N<TAB>akce" pro každý customN.
shortcut_actions() {
  local d n
  for d in $(dconf list "$KEYS/" 2>/dev/null | grep -E '^custom[0-9]+/$' || true); do
    n="${d#custom}"; n="${n%/}"
    printf '%s\t%s\n' "$n" "$(dconf read "$KEYS/custom$n/action" 2>/dev/null || true)"
  done
}

add_shortcut() {
  local binding="$1" action="$BIN_DST toggle"
  if [ "$DRY" = 1 ]; then
    echo "[dry-run] zkontrolovat v dconf $KEYS/customN/action, zda už existuje '$action'"
    echo "[dry-run] dconf write $KEYS/customN/name 'VaultQuick – úkoly'   (N = první volné)"
    echo "[dry-run] dconf write $KEYS/customN/action '$action'"
    echo "[dry-run] dconf write $KEYS/customN/binding '$binding'"
    return
  fi
  command -v dconf >/dev/null || { echo "dconf nenalezen, zkratku nelze založit" >&2; return 1; }
  local existing used n=0
  existing="$(shortcut_actions)"
  if printf '%s\n' "$existing" | cut -f2 | grep -qxF "'$action'"; then
    echo "Zkratka s akcí '$action' už existuje, přeskakuji."
    return
  fi
  used="$(printf '%s\n' "$existing" | cut -f1)"
  while printf '%s\n' "$used" | grep -qx "$n"; do n=$((n + 1)); done
  dconf write "$KEYS/custom$n/name" "'VaultQuick – úkoly'"
  dconf write "$KEYS/custom$n/action" "'$action'"
  dconf write "$KEYS/custom$n/binding" "'$binding'"
  echo "Zkratka $binding přidána jako custom$n."
}

if [ "$UNINSTALL" = 1 ]; then
  run rm -rf "$SHARE"
  run rm -f "$SERVICE_DST" "$BIN_DST"
  run sudo rm -f "$PANEL_DST"
  echo "Odinstalováno. Applet odeberte z lišty a případně smažte zkratku (Klávesové zkratky)"
  echo "a konfiguraci ~/.config/vaultquick-desktop/."
  exit 0
fi

if [ "$SKIP_BUILD" = 0 ]; then
  if [ "$DRY" = 1 ]; then
    echo "[dry-run] (cd $REPO && ./gradlew :desktop:vqd:installDist && ./gradlew --stop)"
  else
    (cd "$REPO" && ./gradlew :desktop:vqd:installDist && ./gradlew --stop)
  fi
fi

BUILD="$REPO/desktop/vqd/build/install/vqd"
if [ "$DRY" = 0 ] && [ ! -x "$BUILD/bin/vqd" ]; then
  echo "Chybí $BUILD/bin/vqd – spusťte bez --skip-build." >&2
  exit 1
fi

# Pomocník vqd (čistá kopie, aby tam nezůstaly staré knihovny).
run rm -rf "$VQD_DST"
run mkdir -p "$VQD_DST"
run cp -a "$BUILD/." "$VQD_DST/"

# Applet (bez cache a testů).
run rm -rf "$APPLET_DST"
run mkdir -p "$APPLET_DST"
run cp -a "$SRC/vqapplet" "$SRC/vaultquick-applet" "$APPLET_DST/"
if [ "$DRY" = 0 ]; then find "$APPLET_DST" -name __pycache__ -type d -prune -exec rm -rf {} +; fi
run chmod +x "$APPLET_DST/vaultquick-applet"

# D-Bus služba a příkaz pro zkratku.
render "$SRC/org.mate.panel.applet.VaultQuickTasksFactory.service.in" "$SERVICE_DST"
run install -D -m755 "$SRC/vaultquick-desktop" "$BIN_DST"

# Soubor appletu pro panel (jednou sudo).
render "$SRC/org.mate.panel.applet.VaultQuickTasks.mate-panel-applet.in" "$PANEL_DST" sudo

[ -n "$SHORTCUT" ] && add_shortcut "$SHORTCUT"

echo "Hotovo. Restartujte panel (mate-panel --replace &) a přidejte applet přes Přidat na panel."
