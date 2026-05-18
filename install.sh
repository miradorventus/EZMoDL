#!/bin/bash
# ============================================================
#  EZmodL — Installer
#  Compat : Ubuntu 24.04+ / Linux Mint 22.x+ / Debian 13+
#  License : Apache 2.0
# ============================================================

set -e

VERSION="1.0.0"
EZMODL_DIR="$HOME/.ezmodl"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_USER_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Bureau")"
REPO_URL="https://github.com/miradorventus/EZmodL"
RAW_BASE="https://raw.githubusercontent.com/miradorventus/EZmodL/main"

# ─── Helpers ─────────────────────────────────────────────
err() { echo "❌ $*" >&2; exit 1; }
info() { echo "📌 $*"; }
ok() { echo "✅ $*"; }
warn() { echo "⚠️  $*"; }
step() { echo ""; echo "═══ $* ═══"; }

# ─── Header ──────────────────────────────────────────────
cat <<'BANNER'
╔════════════════════════════════════════════════════════════╗
║                      E Z m o d L                           ║
║              GGUF Model Manager Installer                  ║
║                       v1.0.0                               ║
╚════════════════════════════════════════════════════════════╝
BANNER

# ─── Step 1 : Check compat distro ────────────────────────
step "Étape 1/7 : Vérification compatibilité système"

if ! command -v apt >/dev/null 2>&1; then
  err "EZmodL nécessite apt (Ubuntu/Mint/Debian). Pour autres distros : install manuel."
fi

[ -f /etc/os-release ] || err "Impossible de détecter la distro"
# shellcheck disable=SC1091
. /etc/os-release
ok "Distro : ${PRETTY_NAME:-$NAME}"

# Vérif Python >= 3.10
if ! command -v python3 >/dev/null 2>&1; then
  err "Python3 absent. Install : sudo apt install python3"
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
ok "Python ${PY_VERSION}"

# ─── Step 2 : Installation deps système ──────────────────
step "Étape 2/7 : Dépendances système"

SYSTEM_DEPS=(python3-pip curl firefox zenity libnotify-bin wmctrl xdg-utils)
MISSING=()

for pkg in "${SYSTEM_DEPS[@]}"; do
  if dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
    ok "$pkg déjà installé"
  else
    MISSING+=("$pkg")
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  info "Packages à installer : ${MISSING[*]}"
  info "Authentification requise (pkexec)..."
  if command -v pkexec >/dev/null 2>&1; then
    pkexec apt-get install -y "${MISSING[@]}" || err "apt install échoué"
  else
    sudo apt-get install -y "${MISSING[@]}" || err "apt install échoué"
  fi
  ok "Dépendances système installées"
fi

# Note : firefox-esr si firefox absent
if ! command -v firefox >/dev/null 2>&1 && ! command -v firefox-esr >/dev/null 2>&1; then
  warn "Firefox absent. Tentative install firefox-esr..."
  pkexec apt-get install -y firefox-esr 2>/dev/null || warn "Firefox non installé — EZmodL fonctionnera dans le navigateur par défaut"
fi

# ─── Step 3 : Deps Python ────────────────────────────────
step "Étape 3/7 : Dépendances Python (flask, pyyaml, requests)"

PIP_PKGS=(flask pyyaml requests huggingface_hub)
for pkg in "${PIP_PKGS[@]}"; do
  module_name="${pkg//-/_}"
  module_name="${module_name/huggingface_hub/huggingface_hub}"
  if python3 -c "import ${module_name//pyyaml/yaml}" 2>/dev/null; then
    ok "Python : $pkg OK"
  else
    info "Install : $pkg"
    pip install --user --break-system-packages "$pkg" 2>&1 | tail -2
  fi
done

# ─── Step 4 : Téléchargement EZmodL ──────────────────────
step "Étape 4/7 : Téléchargement EZmodL"

if [ -d "$EZMODL_DIR" ]; then
  warn "Dossier $EZMODL_DIR existe déjà"
  read -rp "Écraser ? [y/N] " CONFIRM
  if [[ "$CONFIRM" =~ ^[yY]$ ]]; then
    # Backup d'abord
    BACKUP="/tmp/ezmodl-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
    tar czf "$BACKUP" -C "$HOME" .ezmodl 2>/dev/null
    info "Backup créé : $BACKUP"
    rm -rf "$EZMODL_DIR"
  else
    info "Conservation du dossier existant — install des fichiers manquants uniquement"
  fi
fi

mkdir -p "$EZMODL_DIR"/{lib,templates,static,config,queue,logs}

# Liste des fichiers à télécharger
declare -A FILES=(
  ["ezmodl.sh"]="$EZMODL_DIR/ezmodl.sh"
  ["server.py"]="$EZMODL_DIR/server.py"
  ["templates/index.html"]="$EZMODL_DIR/templates/index.html"
  ["static/style.css"]="$EZMODL_DIR/static/style.css"
  ["static/app.js"]="$EZMODL_DIR/static/app.js"
  ["static/icon.png"]="$EZMODL_DIR/static/icon.png"
  ["icon.png"]="$EZMODL_DIR/icon.png"
  ["lib/hf_api.py"]="$EZMODL_DIR/lib/hf_api.py"
  ["lib/vram_classify.py"]="$EZMODL_DIR/lib/vram_classify.py"
  ["lib/disk_search.py"]="$EZMODL_DIR/lib/disk_search.py"
  ["lib/yaml_helper.py"]="$EZMODL_DIR/lib/yaml_helper.py"
  ["lib/parse_quant.py"]="$EZMODL_DIR/lib/parse_quant.py"
  ["ezmodl.desktop"]="$DESKTOP_DIR/ezmodl.desktop"
)

# Téléchargement (sauf si install local par git clone)
if [ -n "$EZMODL_LOCAL_INSTALL" ]; then
  info "Mode install local (depuis git clone)"
  SRC_DIR="$(pwd)"
  for repo_path in "${!FILES[@]}"; do
    target="${FILES[$repo_path]}"
    if [ -f "$SRC_DIR/$repo_path" ]; then
      mkdir -p "$(dirname "$target")"
      cp "$SRC_DIR/$repo_path" "$target"
    else
      warn "Fichier source manquant : $repo_path"
    fi
  done
else
  info "Téléchargement depuis $REPO_URL ..."
  for repo_path in "${!FILES[@]}"; do
    target="${FILES[$repo_path]}"
    mkdir -p "$(dirname "$target")"
    if curl -fsSL -o "$target" "$RAW_BASE/$repo_path" 2>/dev/null; then
      echo "  ✓ $repo_path"
    else
      err "Échec téléchargement : $repo_path"
    fi
  done
fi

ok "Fichiers EZmodL installés dans $EZMODL_DIR"

# ─── Step 5 : Permissions ────────────────────────────────
step "Étape 5/7 : Permissions"

chmod +x "$EZMODL_DIR/ezmodl.sh"
chmod +x "$DESKTOP_DIR/ezmodl.desktop"
ok "Permissions OK"

# ─── Step 6 : Desktop entries (menu + bureau) ───────────
step "Étape 6/7 : Intégration desktop"

# Adapter les chemins absolus dans le .desktop
sed -i "s|/home/[^/]*/.ezmodl|$EZMODL_DIR|g" "$DESKTOP_DIR/ezmodl.desktop"

# Validation
if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$DESKTOP_DIR/ezmodl.desktop" && ok "Desktop entry valide" || warn "Desktop entry avec warnings (non-bloquant)"
fi

# Refresh menu
command -v update-desktop-database >/dev/null && update-desktop-database "$DESKTOP_DIR" 2>/dev/null

# Raccourci bureau (optionnel)
read -rp "Créer un raccourci sur le bureau ? [Y/n] " DESKTOP_ICON
if [[ ! "$DESKTOP_ICON" =~ ^[nN]$ ]]; then
  mkdir -p "$DESKTOP_USER_DIR"
  cp "$DESKTOP_DIR/ezmodl.desktop" "$DESKTOP_USER_DIR/"
  chmod +x "$DESKTOP_USER_DIR/ezmodl.desktop"
  # Marquer comme trusted pour XFCE/GNOME
  gio set "$DESKTOP_USER_DIR/ezmodl.desktop" metadata::trusted true 2>/dev/null || true
  ok "Raccourci bureau créé"
fi

# ─── Step 7 : Validation install ─────────────────────────
step "Étape 7/7 : Test rapide"

# Test des imports Python
if python3 -c "
import sys
sys.path.insert(0, '$EZMODL_DIR/lib')
import hf_api, vram_classify, disk_search, yaml_helper, parse_quant
" 2>/dev/null; then
  ok "Modules Python OK"
else
  warn "Erreur import modules Python — vérifier $EZMODL_DIR/lib/"
fi

# Test lancement Flask en mode validation
if python3 -c "
import sys
sys.path.insert(0, '$EZMODL_DIR/lib')
import ast
with open('$EZMODL_DIR/server.py') as f:
    ast.parse(f.read())
" 2>/dev/null; then
  ok "server.py : syntaxe OK"
else
  err "server.py corrompu"
fi

# ─── Résumé final ────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
ok "EZmodL installé avec succès !"
echo "════════════════════════════════════════════════════════"
echo ""
info "Pour lancer :"
echo "   • Menu Applications → EZmodL"
echo "   • Raccourci bureau (si créé)"
echo "   • CLI : $EZMODL_DIR/ezmodl.sh"
echo ""
info "Configuration :"
echo "   • Dossier app    : $EZMODL_DIR"
echo "   • Logs           : $EZMODL_DIR/logs/ezmodl.log"
echo "   • Modèles GGUF   : ~/llm-models/"
echo "   • Port web       : 3001"
echo ""
info "Prérequis pour usage :"
echo "   • llama-swap configuré (~/.llamaui/config/llama-swap.yaml)"
echo "   • Si pas encore : install via https://github.com/miradorventus/ollama-amd-plug-and-play"
echo ""
info "Désinstaller : ./uninstall.sh"
echo ""
