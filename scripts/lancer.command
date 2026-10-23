#!/usr/bin/env bash
# Lance BeeDoo : le daemon du robot (s'il ne tourne pas déjà) puis l'application.
# Double-clic dans le Finder, ou :  scripts/lancer.command
#
# Ctrl+C arrête BeeDoo, et le daemon seulement s'il a été lancé par ce script.
set -euo pipefail

RACINE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RACINE"

if [ ! -d .venv ]; then
    echo "BeeDoo n'est pas installé : lance d'abord scripts/install.sh"
    read -r -p "Appuie sur Entrée pour fermer."
    exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# Charge .env seulement pour lire l'adresse du daemon (la clé reste lue par BeeDoo lui-même).
URL_DAEMON="${BEEDOO_DAEMON_URL:-$(sed -n 's/^BEEDOO_DAEMON_URL=//p' .env 2>/dev/null | tail -1)}"
URL_DAEMON="${URL_DAEMON:-http://127.0.0.1:8000}"

DAEMON_PID=""
arreter() {
    if [ -n "$DAEMON_PID" ]; then
        kill "$DAEMON_PID" 2>/dev/null || true
    fi
}
trap arreter EXIT

# Un daemon répond déjà (application « Reachy Mini Control » ou lancement précédent) : on s'en sert.
# Jamais deux daemons en même temps (même port).
if curl -s -o /dev/null --max-time 2 "$URL_DAEMON/"; then
    echo "Un daemon répond déjà sur $URL_DAEMON : je l'utilise."
else
    echo "Démarrage du daemon du robot…"
    reachy-mini-daemon &
    DAEMON_PID=$!
    for _ in $(seq 1 40); do
        if curl -s -o /dev/null --max-time 2 "$URL_DAEMON/"; then
            break
        fi
        if ! kill -0 "$DAEMON_PID" 2>/dev/null; then
            echo "Le daemon s'est arrêté. Le robot est-il branché et allumé ?"
            DAEMON_PID=""
            read -r -p "Appuie sur Entrée pour fermer."
            exit 1
        fi
        sleep 1
    done
fi

# Version du SDK = version du daemon, toujours. On compare et on propose d'aligner le SDK.
VERSION_DAEMON="$(curl -s --max-time 3 "$URL_DAEMON/api/daemon/status" \
    | python -c 'import json,sys; print(json.load(sys.stdin).get("version", ""))' 2>/dev/null || true)"
VERSION_SDK="$(python -c 'from importlib.metadata import version; print(version("reachy-mini"))' 2>/dev/null || true)"
if [ -n "$VERSION_DAEMON" ] && [ -n "$VERSION_SDK" ] && [ "$VERSION_DAEMON" != "$VERSION_SDK" ]; then
    echo "Versions différentes : SDK $VERSION_SDK, daemon $VERSION_DAEMON."
    read -r -p "Installer reachy-mini==$VERSION_DAEMON dans le venv ? [O/n] " REPONSE
    case "${REPONSE:-O}" in
        [nN]*) echo "Je continue sans aligner (des problèmes sont possibles)." ;;
        *) python -m pip install "reachy-mini==$VERSION_DAEMON" ;;
    esac
fi

echo "Démarrage de BeeDoo (Ctrl+C pour arrêter)."
python -m beedoo.main
