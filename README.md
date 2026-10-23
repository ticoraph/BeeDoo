# BeeDoo

BeeDoo est un robot d'accompagnement basé sur un [Reachy Mini](https://github.com/pollen-robotics/reachy_mini) (Pollen Robotics). Il parle français comme un enfant de 7 ans, reconnaît les visages et dit bonjour par le prénom, propose une quinzaine de mini-applications (blague Toto, météo, actualités…) et apprend à connaître les personnes au fil des conversations.

> **État du projet : en construction.** Le cadrage est fait, l'application se construit phase par phase.

## Ce qu'il faut

- Un Reachy Mini (Lite, branché en USB, ou Wireless), ou le mode simulation du SDK pour essayer sans robot.
- Python 3.12 et git.
- Pour la conversation (à venir) : une clé API OpenAI (LLM, reconnaissance vocale et synthèse vocale).

## Installation

```bash
# 1. Récupérer le dépôt avec le SDK (sous-module git)
git clone --recurse-submodules https://github.com/ticoraph/BeeDoo.git
cd BeeDoo

# 2. Créer l'environnement Python et installer BeeDoo (avec les outils de développement)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Activer les garde-fous contre les fuites de secrets (si tu contribues)
pre-commit install

# 4. Préparer la configuration (à compléter quand l'application utilisera les clés)
cp .env.example .env
```

Si tu as cloné sans `--recurse-submodules` : `git submodule update --init`.

Vérifier que tout est en place : `pytest`.

**Reconnaissance de visage** : elle se fait sur ta machine avec DeepFace (installé par `requirements.txt`, avec OpenCV `headless`). N'installe pas `opencv-python` à côté : deux paquets OpenCV se cassent mutuellement. Au premier usage, les modèles (environ 100 Mo) sont téléchargés depuis GitHub dans `~/.deepface/` : il faut donc un accès à GitHub une fois.

## Essayer le robot

Dans un premier terminal, lancer le daemon du robot (ou `reachy-mini-daemon --sim` pour la simulation) :

```bash
source .venv/bin/activate
reachy-mini-daemon
```

Dans un second terminal :

```bash
source .venv/bin/activate
python examples/test_connection.py
```

Le robot doit bouger la tête et les antennes pendant quelques secondes. Si l'application officielle « Reachy Mini Control » est ouverte, ferme-la : elle utilise le même port que le daemon.

### Sans robot : la simulation

Pour développer sans robot, installe l'option de simulation (MuJoCo), puis lance le daemon en mode `--sim` à la place du daemon habituel :

```bash
source .venv/bin/activate
pip install -e ".[sim]"
mjpython -m reachy_mini.daemon.app.main --sim    # macOS
reachy-mini-daemon --sim                         # Linux et Windows
```

BeeDoo se connecte ensuite exactement comme avec le vrai robot (`python -m beedoo.main`). Ne lance jamais deux daemons en même temps (même port 8000). En simulation, la carte audio du robot est absente : BeeDoo utilise le micro et les haut-parleurs de l'ordinateur, avec une annulation d'écho logicielle (moins fiable que celle du robot). L'écoute se règle donc au final avec le vrai robot.

### Version du SDK

Le SDK (`reachy-mini`, installé dans le venv) et le daemon doivent toujours avoir **la même version**. Si tu utilises l'application officielle « Reachy Mini Control », son daemon se met à jour avant le SDK : après une mise à jour, aligne le SDK.

Un écart déclenche, à la connexion, un avertissement qui donne les deux versions :

```
Reachy Mini SDK and daemon versions do not match: SDK=1.10.0, daemon=1.11.0
```

Dans ce cas, installe la version du daemon, puis relance `pytest` :

```bash
pip install "reachy-mini==1.11.0"
```

## Interface web

Quand BeeDoo tourne, une page locale affiche son état et un bouton pour couper l'écoute (muet) :

```
http://127.0.0.1:8765
```

- Elle n'écoute que sur ta machine (`127.0.0.1`), jamais sur le réseau, et ne charge rien depuis Internet.
- Le port se change avec `BEEDOO_WEB_PORT` dans `.env`. Si le port est déjà pris, BeeDoo démarre quand même, sans la page.
- Elle n'affiche et ne demande aucune clé API : elles restent dans `.env`.
- Le réglage « muet » est enregistré dans `data/settings.json` (ignoré par git).

## Vie privée

BeeDoo manipule des données sensibles : visages, voix, conversations.

- Tout ce qui concerne les personnes est stocké **localement**, dans le dossier `data/`, qui n'est jamais versionné.
- Les clés API sont dans `.env`, qui n'est jamais versionné.
- La reconnaissance de visage tourne en local. En revanche, le texte et l'audio des conversations sont envoyés à OpenAI. Informe les personnes concernées et respecte leur choix.
- Si tu contribues : ne pousse jamais de clé, de photo, d'enregistrement, de vraie conversation, de prénom de vraie personne ni de chemin personnel. Les exemples et les tests n'utilisent que des personnes fictives. Les garde-fous `pre-commit` vérifient une partie de ces règles.

## Organisation du dépôt

| Dossier | Contenu |
|---|---|
| `prompts/` | Personnalité de BeeDoo (prompt du LLM) |
| `src/beedoo/` | Code de l'application (gestes, vision, voix, LLM, mémoire, mini-apps, interface) |
| `tests/` | Tests |
| `scripts/` | Petits outils (photo, enregistrement audio) |
| `examples/` | Essais de connexion au robot |
| `reachy_mini/` | SDK officiel (sous-module git, lecture seule) |

## Licence

Copyright 2026 BeeDoo contributors.

BeeDoo est distribué sous licence [Apache 2.0](LICENSE). Le SDK `reachy_mini` (sous-module) a sa propre licence, également Apache 2.0.
