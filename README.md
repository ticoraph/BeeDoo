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
