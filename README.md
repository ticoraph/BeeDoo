# BeeDoo

BeeDoo est un robot d'accompagnement basé sur un [Reachy Mini](https://github.com/pollen-robotics/reachy_mini) (Pollen Robotics). Il parle français comme un enfant de 7 ans, reconnaît les visages et dit bonjour par le prénom, propose une quinzaine de mini-applications (blague Toto, météo, actualités…) et apprend à connaître les personnes au fil des conversations.

> **État du projet : en construction.** Le cadrage est fait, l'application n'existe pas encore. Voir [docs/PROJECT.md](docs/PROJECT.md) pour la vision et [docs/PLAN.md](docs/PLAN.md) pour l'avancement.

## Ce qu'il faut

- Un Reachy Mini (Lite, branché en USB, ou Wireless), ou le mode simulation du SDK pour essayer sans robot.
- Python 3.12 et git.
- Pour la conversation (à venir) : une clé API OpenAI et une clé API ElevenLabs.

## Installation

```bash
# 1. Récupérer le dépôt avec le SDK (sous-module git)
git clone --recurse-submodules https://github.com/ticoraph/BeeDoo.git
cd BeeDoo

# 2. Créer l'environnement Python et installer les dépendances
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Préparer la configuration (à compléter quand l'application utilisera les clés)
cp .env.example .env
```

Si tu as cloné sans `--recurse-submodules` : `git submodule update --init`.

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
- La reconnaissance de visage tourne en local. En revanche, le texte et l'audio des conversations sont envoyés à OpenAI et ElevenLabs. Informe les personnes concernées et respecte leur choix.
- Si tu contribues : lis les règles de la section « Dépôt public » de [CLAUDE.md](CLAUDE.md). Ne pousse jamais de photo, d'enregistrement ou de vraie conversation.

## Organisation du dépôt

| Dossier | Contenu |
|---|---|
| `docs/` | Vision, plan, décisions |
| `prompts/` | Personnalité de BeeDoo (prompt du LLM) |
| `scripts/` | Petits outils (photo, enregistrement audio) |
| `examples/` | Essais de connexion au robot |
| `reachy_mini/` | SDK officiel (sous-module git, lecture seule) |

## Licence

Copyright 2026 BeeDoo contributors.

BeeDoo est distribué sous licence [Apache 2.0](LICENSE). Le SDK `reachy_mini` (sous-module) a sa propre licence, également Apache 2.0.
