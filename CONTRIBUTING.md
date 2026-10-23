# Contribuer à BeeDoo

Merci de t'intéresser à BeeDoo ! C'est un petit projet : un robot de compagnie qui parle français comme un enfant de 7 ans. Les contributions sont les bienvenues (corrections, nouvelles mini-applications, traductions des messages, documentation), à condition de respecter **une règle avant toutes les autres**.

## La règle d'or : rien de personnel dans le dépôt

BeeDoo manipule des visages, des voix et des conversations. Ce dépôt est **public** : tout ce qui y est écrit est lisible par tous, pour toujours, même après suppression.

**Ne publie jamais** (ni dans un commit, ni dans une issue, ni dans une pull request) :

- une clé d'API, un fichier `.env`, un mot de passe ;
- le contenu de `data/` (visages, empreintes, conversations, souvenirs, réglages) ;
- une photo, un enregistrement audio, une transcription, une vraie conversation, même anonymisée ;
- le prénom ou une information sur une vraie personne ;
- un chemin absolu qui contient ton nom d'utilisateur (ceux qui commencent par `/Users/` sous macOS ou `/home/` sous Linux, suivis de ton nom), le nom de ta machine, une adresse IP, une adresse e-mail.

Pour les exemples, les tests et les captures d'écran, utilise des personnes **fictives** (« Mamie Jeanne », « Léa »). L'interface de démonstration (`python scripts/demo_interface.py`) n'affiche que des données inventées ; c'est elle qui produit les captures du dossier `captures/`, seul endroit où une image est acceptée.

Si tu as publié par erreur quelque chose de personnel, **dis-le tout de suite** (voir `SECURITY.md`) : on ne réécrit pas l'historique à la légère, mais on agit vite.

## Installer et vérifier

```bash
git clone --recurse-submodules https://github.com/ticoraph/BeeDoo.git
cd BeeDoo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pre-commit install        # active les garde-fous contre les fuites de secrets et de données
pytest                    # tous les tests doivent passer
```

Le détail (robot, simulation, version du SDK) est dans le `README.md`. Pas de robot ? La simulation et l'interface de démonstration suffisent pour la plupart des changements.

Les garde-fous `pre-commit` (détection de secrets, fichiers personnels, chemins personnels) tournent aussi sur GitHub. Si l'un d'eux refuse ton commit, **n'essaie pas de le contourner** (`--no-verify`, `git add -f`) : corrige la cause.

## Écrire du code

- **Langue** : tout ce que BeeDoo dit est en français, avec des phrases courtes et des mots simples. Le code et les identifiants peuvent être en anglais ; les commentaires, la documentation et les messages de commit en français, comme le reste du dépôt.
- **Tests** : un changement de comportement s'accompagne d'un test. Les tests n'ont besoin ni du robot ni d'Internet (voir les faux robots dans `tests/`). Utilise des données fictives, et des fausses clés qui ne ressemblent pas à de vraies (le détecteur de secrets les repérerait).
- **Mouvements** : `goto_target()` d'au moins 0,5 s par geste ; `set_target()` seulement pour les boucles temps réel. Voir `reachy_mini/skills/`.
- **Configuration** : tout ce qui change d'une machine ou d'une personne à l'autre (clés, voix, ville, chemins) se lit dans `.env` ou `data/`, jamais en dur dans le code.
- **Journaux** : jamais de clé, de prénom, ni de texte de conversation dans les logs.
- **Nouvelle dépendance ou étape manuelle** : ajoute-la au `README.md` (et à `.env.example` si elle touche une clé). Ne suppose jamais qu'un outil existe seulement chez toi.
- **Le dossier `reachy_mini/`** est le SDK officiel, en sous-module et en lecture seule : ne le modifie pas.

### Ajouter une mini-application

1. Crée un fichier dans `src/beedoo/miniapps/` avec une classe `MiniApp` (voir `base.py` et un exemple court : `heure.py`) : mots-clés « sûrs » (elle se lance tout de suite) et « vagues » (BeeDoo demande d'abord confirmation), une phrase de proposition, et `repondre()`.
2. Ajoute-la à `toutes()` dans `src/beedoo/miniapps/__init__.py`.
3. Écris ses tests : les phrases qui doivent la déclencher, et surtout celles qui **ne** doivent **pas** (« je suis à l'heure » ne déclenche pas l'heure).
4. Si elle appelle un service sur Internet, dis-le dans le `README.md` : quelle donnée part, vers qui. Préfère un service gratuit sans clé.

### Toucher à la personnalité de BeeDoo

Les fichiers de `prompts/` définissent ce que BeeDoo dit à des personnes parfois fragiles. Modifie-les avec soin et explique le pourquoi dans ta pull request : phrases courtes, tutoiement, pas de conseil médical, orientation vers les secours en cas de danger.

## Proposer un changement

1. Ouvre d'abord une issue pour un changement important (une idée, une nouvelle fonction), afin d'être sûr qu'il va dans le sens du projet.
2. Fais une branche, des commits petits et clairs, puis une pull request avec le modèle proposé.
3. Avant d'envoyer : `pytest` et `pre-commit run --all-files` passent, et tu as relu le diff (`git diff`) à la recherche de tout ce que la règle d'or interdit.

## Signaler un problème

Utilise les modèles d'issue. **Ne colle pas** ton terminal en entier : il peut contenir des chemins ou des noms. Colle plutôt le contenu de l'onglet **Journal** de l'interface, qui est nettoyé des clés et des chemins personnels, et relis-le avant d'envoyer.

Pour une faille de sécurité ou une fuite de données, ne crée pas d'issue publique avec les détails : lis `SECURITY.md`.
