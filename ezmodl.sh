#!/bin/bash
# ============================================================
#  ezmodl.sh — Launcher EZmodL (manager GGUF pour llama-swap)
#  Version: 1.0.0
#  Pattern: identique à ollamaui-launcher.sh / llamaui-launcher.sh
# ============================================================

VERSION="1.0.0"
LOCKFILE="/tmp/ezmodl.lock"

EZMODL_DIR="$HOME/.ezmodl"
EZMODL_PORT="3001"
EZMODL_URL="http://127.0.0.1:${EZMODL_PORT}"
EZMODL_LOG="$EZMODL_DIR/logs/ezmodl.log"
EZMODL_PIDFILE="$EZMODL_DIR/ezmodl.pid"
EZMODL_SERVER="$EZMODL_DIR/server.py"

# Profil Firefox dédié (isolation WebApp)
FFOX_PROFILE_DIR="$HOME/.mozilla/firefox/ezmodl"

mkdir -p "$EZMODL_DIR/logs"

# ─── Manual stop via CLI ────────────────────────────────────
if [ "$1" = "--stop" ]; then
  echo "🛑 Stopping EZmodL..."
  if [ -f "$EZMODL_PIDFILE" ]; then
    EZ_PID=$(cat "$EZMODL_PIDFILE")
    kill "$EZ_PID" 2>/dev/null && echo "→ Flask killed (PID $EZ_PID)"
    rm -f "$EZMODL_PIDFILE"
  fi
  pkill -f "python3.*$EZMODL_SERVER" 2>/dev/null && echo "→ Flask orphans killed"
  rm -f "$LOCKFILE"
  echo "✅ Stopped"
  exit 0
fi

# ─── Helper popup d'erreur ──────────────────────────────────
error_popup() {
  zenity --error --title="EZmodL — Error" --text="$1" \
    --extra-button="View log" --width=450 2>/dev/null
  [ $? -eq 1 ] && zenity --text-info --title="Logs" \
    --filename="$EZMODL_LOG" --width=700 --height=400 2>/dev/null
}

# ─── Helper toast notification ──────────────────────────────
toast() {
  notify-send -i "$EZMODL_DIR/icon.png" -t 3000 "EZmodL" "$1" 2>/dev/null
}

# ============================================================
# STEP 1 — ALREADY RUNNING ?
# ============================================================
if [ -f "$LOCKFILE" ]; then
  OLD_PID=$(cat "$LOCKFILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    zenity --info --title="EZmodL — Already running" \
      --text="EZmodL tourne déjà.\n\nL'interface s'est ouverte dans un profil Firefox isolé.\nCherche la fenêtre Firefox EZmodL\nsur ${EZMODL_URL}\n\nPour redémarrer : ferme cette fenêtre Firefox d'abord." \
      --width=450 --timeout=8 2>/dev/null
    exit 0
  else
    rm -f "$LOCKFILE"
  fi
fi

# ============================================================
# STEP 2 — INTEGRITY CHECK
# ============================================================
MISSING=()
[ ! -f "$EZMODL_SERVER" ] && MISSING+=("server.py")
[ ! -f "$EZMODL_DIR/templates/index.html" ] && MISSING+=("templates/index.html")
[ ! -f "$EZMODL_DIR/static/style.css" ] && MISSING+=("static/style.css")
[ ! -f "$EZMODL_DIR/static/app.js" ] && MISSING+=("static/app.js")
[ ! -f "$EZMODL_DIR/static/icon.png" ] && MISSING+=("static/icon.png")
[ ! -d "$EZMODL_DIR/lib" ] && MISSING+=("lib/")

if [ ${#MISSING[@]} -gt 0 ]; then
  LIST=""
  for f in "${MISSING[@]}"; do LIST+="• $f\n"; done
  error_popup "Fichiers EZmodL manquants :\n\n${LIST}\nRéinstalle EZmodL."
  exit 1
fi

# Check Python + Flask
if ! command -v python3 >/dev/null 2>&1; then
  error_popup "Python3 absent. Install : sudo apt install python3 python3-pip"
  exit 1
fi
if ! python3 -c "import flask" 2>/dev/null; then
  zenity --question --title="EZmodL — Dependencies" \
    --text="Flask manquant. Installer maintenant ?\n\nCommande :\npip install --user --break-system-packages flask" \
    --width=400 2>/dev/null
  if [ $? -eq 0 ]; then
    pip install --user --break-system-packages flask 2>&1 | tail -5
  else
    exit 1
  fi
fi

# Check curl (nécessaire pour download)
if ! command -v curl >/dev/null 2>&1; then
  error_popup "curl absent (nécessaire pour téléchargements).\nInstall : sudo apt install curl"
  exit 1
fi

# ============================================================
# STEP 3 — FIREFOX DETECTION
# ============================================================
FIREFOX_BIN=""
for candidate in firefox firefox-esr; do
  if command -v "$candidate" >/dev/null 2>&1; then
    FIREFOX_BIN="$candidate"
    break
  fi
done

if [ -z "$FIREFOX_BIN" ]; then
  error_popup "Firefox introuvable. Install : sudo apt install firefox"
  exit 1
fi

# ============================================================
# STEP 4 — PROFIL FIREFOX DÉDIÉ
# ============================================================
if [ ! -d "$FFOX_PROFILE_DIR" ]; then
  mkdir -p "$FFOX_PROFILE_DIR"
  # Crée le profil sans le lancer
  "$FIREFOX_BIN" -CreateProfile "ezmodl $FFOX_PROFILE_DIR" 2>/dev/null
  toast "Profil Firefox EZmodL créé"
fi

# ============================================================
# STEP 5 — DÉMARRAGE FLASK
# ============================================================
# Lockfile + cleanup trap
echo $$ > "$LOCKFILE"
trap cleanup EXIT INT TERM

cleanup() {
  EXIT_CODE=$?
  # Garde-fou : éviter double exécution (trap EXIT + appel explicite)
  [ -n "$CLEANUP_DONE" ] && return
  CLEANUP_DONE=1
  # Kill Flask
  if [ -f "$EZMODL_PIDFILE" ]; then
    EZ_PID=$(cat "$EZMODL_PIDFILE")
    kill "$EZ_PID" 2>/dev/null
    rm -f "$EZMODL_PIDFILE"
  fi
  pkill -f "python3.*$EZMODL_SERVER" 2>/dev/null
  rm -f "$LOCKFILE"
  notify-send -i "$EZMODL_DIR/icon.png" -t 2500 "EZmodL" "✅ Arrêté proprement" 2>/dev/null
  exit $EXIT_CODE
}

# Si Flask déjà actif sur le port, on ne relance pas
if curl -s --max-time 1 "$EZMODL_URL/api/health" > /dev/null 2>&1; then
  echo "→ Flask déjà actif sur $EZMODL_PORT"
else
  echo "→ Démarrage Flask..."
  cd "$EZMODL_DIR" || { error_popup "Cannot cd to $EZMODL_DIR"; exit 1; }
  nohup python3 "$EZMODL_SERVER" --port "$EZMODL_PORT" > "$EZMODL_LOG" 2>&1 &
  FLASK_PID=$!
  echo "$FLASK_PID" > "$EZMODL_PIDFILE"
  
  # Attente démarrage (max 10s)
  for i in {1..20}; do
    if curl -s --max-time 1 "$EZMODL_URL/api/health" > /dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
  
  # Vérif final
  if ! curl -s --max-time 1 "$EZMODL_URL/api/health" > /dev/null 2>&1; then
    error_popup "Flask n'a pas démarré après 10s.\nVoir les logs."
    exit 1
  fi
fi

# Toast de confirmation
toast "EZmodL démarré sur ${EZMODL_URL}"

# ============================================================
# STEP 6 — LANCER FIREFOX EN WEBAPP
# ============================================================
"$FIREFOX_BIN" \
  --profile "$FFOX_PROFILE_DIR" \
  --class "WebApp-EZmodL" \
  --name "WebApp-EZmodL" \
  --new-window "$EZMODL_URL" &
FIREFOX_PID=$!

# ============================================================
# STEP 7 — ATTENTE FIREFOX → CLEANUP À LA FERMETURE
# ============================================================
# Attend que Firefox ferme la fenêtre EZmodL
# On surveille via wmctrl si dispo, sinon polling via process
if command -v wmctrl >/dev/null 2>&1; then
  # Attendre que la fenêtre apparaisse
  for i in {1..10}; do
    if wmctrl -l 2>/dev/null | grep -qi "ezmodl"; then break; fi
    sleep 0.5
  done
  # Attendre que la fenêtre disparaisse
  while wmctrl -l 2>/dev/null | grep -qi "ezmodl"; do
    sleep 1
  done
else
  # Fallback : attendre le PID Firefox (mais ça attend toute l'instance Firefox)
  # Plus simple : on attend que le user ferme via Ctrl+C ou kill
  # Note : sans wmctrl, le launcher reste actif jusqu'au kill manuel
  while kill -0 "$FIREFOX_PID" 2>/dev/null; do
    sleep 2
  done
fi

# Cleanup explicite (au cas où trap ne se déclenche pas)
cleanup
