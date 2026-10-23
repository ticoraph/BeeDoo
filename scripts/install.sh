#!/usr/bin/env bash
# Installe BeeDoo sur un Mac : environnement Python, dépendances, fichier .env.
#
#   scripts/install.sh
#
# Peut être relancé sans risque : ce qui existe déjà (venv, .env) n'est pas écrasé.
# Compatible avec le bash 3.2 fourni par macOS.
set -euo pipefail

RACINE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RACINE"

echo "== BeeDoo : installation =="

# 1. Python 3.12 (ou plus récent)
PYTHON=""
for candidat in python3.12 python3.13 python3; do
    if command -v "$candidat" >/dev/null 2>&1 && "$candidat" -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
        PYTHON="$candidat"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "Python 3.12 ou plus récent est introuvable."
    echo "Installe-le (par exemple : brew install python@3.12), puis relance ce script."
    exit 1
fi
echo "Python : $($PYTHON --version)"

# 2. Environnement virtuel
if [ ! -d .venv ]; then
    echo "Création de l'environnement .venv…"
    "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 3. Dépendances (BeeDoo en mode éditable, avec pytest et pre-commit)
echo "Installation des dépendances (quelques minutes la première fois)…"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

# 4. Configuration
if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    echo ".env créé à partir de .env.example."
else
    echo ".env existe déjà : laissé tel quel."
fi

# 5. Garde-fous contre les fuites de secrets (seulement si on est dans un dépôt git)
if [ -d .git ]; then
    pre-commit install >/dev/null && echo "Garde-fous pre-commit activés."
fi

# 6. Vérification
echo "Lancement des tests…"
if python -m pytest -q; then
    echo "Tests : OK."
else
    echo "Des tests échouent : voir ci-dessus avant d'aller plus loin."
fi

cat <<'FIN'

== Il reste à faire à la main ==

1. Ouvrir .env et renseigner OPENAI_API_KEY (la clé n'est pas dans git).
2. Brancher le robot, puis le lancer :  scripts/lancer.command
   (ou, à la main : reachy-mini-daemon dans un terminal, python -m beedoo.main dans un autre).
3. Accepter les demandes d'accès à la caméra et au micro de macOS pour le Terminal.
4. Au premier usage, DeepFace télécharge ses modèles (environ 100 Mo) : il faut un accès à GitHub.
5. Si la connexion affiche « SDK and daemon versions do not match » :
   pip install "reachy-mini==<version du daemon>"
FIN
