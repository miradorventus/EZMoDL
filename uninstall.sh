#!/bin/bash
# ============================================================
#  EZmodL — Uninstaller
# ============================================================

set -e

EZMODL_DIR="$HOME/.ezmodl"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_USER_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Bureau")"
FFOX_PROFILE_DIR="$HOME/.mozilla/firefox/ezmodl"

echo "═══ Désinstallation EZmodL ═══"
echo ""

# Stop Flask si actif
if [ -f "$EZMODL_DIR/ezmodl.sh" ]; then
  echo "→ Arrêt du service..."
  "$EZMODL_DIR/ezmodl.sh" --stop 2>/dev/null || true
fi

# Kill processes éventuels
pkill -f "python3.*$EZMODL_DIR/server.py" 2>/dev/null || true
rm -f /tmp/ezmodl.lock 2>/dev/null

# Backup avant suppression
if [ -d "$EZMODL_DIR" ]; then
  BACKUP="/tmp/ezmodl-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
  read -rp "Créer un backup avant suppression ? [Y/n] " BACK
  if [[ ! "$BACK" =~ ^[nN]$ ]]; then
    tar czf "$BACKUP" -C "$HOME" .ezmodl 2>/dev/null
    echo "✅ Backup : $BACKUP"
  fi
fi

# Suppression des fichiers
echo ""
echo "→ Suppression des fichiers..."

[ -d "$EZMODL_DIR" ] && rm -rf "$EZMODL_DIR" && echo "  ✓ $EZMODL_DIR"
[ -f "$DESKTOP_DIR/ezmodl.desktop" ] && rm -f "$DESKTOP_DIR/ezmodl.desktop" && echo "  ✓ Menu entry"
[ -f "$DESKTOP_USER_DIR/ezmodl.desktop" ] && rm -f "$DESKTOP_USER_DIR/ezmodl.desktop" && echo "  ✓ Raccourci bureau"

# Profil Firefox dédié
if [ -d "$FFOX_PROFILE_DIR" ]; then
  read -rp "Supprimer le profil Firefox dédié ? [y/N] " RMFFOX
  if [[ "$RMFFOX" =~ ^[yY]$ ]]; then
    rm -rf "$FFOX_PROFILE_DIR"
    echo "  ✓ Profil Firefox"
  fi
fi

# Refresh menu
command -v update-desktop-database >/dev/null && update-desktop-database "$DESKTOP_DIR" 2>/dev/null

echo ""
echo "✅ EZmodL désinstallé"
echo ""
echo "Note : les modèles GGUF dans ~/llm-models/ sont conservés."
echo "       La config llama-swap n'est pas modifiée."
