#!/usr/bin/env bash
# Régénère les captures d'écran de captures/ à partir de l'interface de démonstration (données FICTIVES).
#
#   scripts/faire_captures.sh
#
# Nécessite Google Chrome (variable CHROME pour un autre chemin) et l'environnement BeeDoo activé.
# Jamais de vraie personne ni de vraie conversation : tout vient de scripts/demo_interface.py.
set -euo pipefail

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
PORT=8799
RACINE="$(cd "$(dirname "$0")/.." && pwd)"
PROFIL="$(mktemp -d)"
trap 'kill "${DEMO_PID:-}" 2>/dev/null || true; rm -rf "$PROFIL"' EXIT

python "$RACINE/scripts/demo_interface.py" --port "$PORT" --duree 120 >/dev/null 2>&1 &
DEMO_PID=$!
sleep 4

capture() {  # nom, hauteur
  "$CHROME" --headless=new --disable-gpu --user-data-dir="$PROFIL" --hide-scrollbars \
    --window-size=560,"$2" --virtual-time-budget=6000 \
    --screenshot="$RACINE/captures/$1.png" "http://127.0.0.1:$PORT/#$1" >/dev/null 2>&1
  echo "captures/$1.png"
}

capture etat 1010
capture reglages 1010
capture personnes 590
capture journal 620
