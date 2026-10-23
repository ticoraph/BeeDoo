# Sécurité

BeeDoo manipule des données sensibles (visages, voix, conversations). Merci de signaler tout problème avec soin.

## Signaler une faille ou une fuite de données

**Ne publie pas les détails dans une issue publique.**

- Si le dépôt propose **« Report a vulnerability »** (onglet *Security* de GitHub), utilise-le : le signalement reste privé.
- Sinon, ouvre une issue qui dit seulement « **Sécurité : je souhaite un contact privé** », **sans aucun détail technique ni donnée personnelle**. La personne qui gère le dépôt te répondra pour continuer en privé.

Sont concernés, par exemple : une clé d'API, une photo, un enregistrement, un prénom ou une conversation réels apparaissant dans le dépôt ou son historique ; une façon de lire ou d'effacer des souvenirs sans y être autorisé ; un contournement du mot de passe de l'interface.

Si **tu** as publié par erreur quelque chose de personnel ou un secret : fais-le savoir tout de suite et, s'il s'agit d'une clé, **révoque-la chez son fournisseur d'abord** (elle est compromise dès qu'elle a été publiée, même retirée ensuite). Réécrire l'historique git n'efface pas les copies et les caches : ce n'est qu'une étape.

## Ce que BeeDoo protège, et ses limites

- Les données des personnes (empreintes de visage, souvenirs, conversations enregistrées avec accord) restent dans `data/`, jamais versionné, avec des droits limités à l'utilisateur. Les images de la caméra ne sont ni enregistrées ni envoyées.
- Le texte et l'audio des conversations, le texte des salutations (avec le prénom) et le nom de la ville (météo) sont envoyés à des services externes : voir la section *Vie privée* du `README.md`.
- L'interface web n'écoute que sur l'ordinateur de BeeDoo (`127.0.0.1`). L'ouverture au réseau local est facultative, réglée dans `.env`, protégée par un mot de passe, et **n'est pas chiffrée (http)** : à réserver à un réseau domestique de confiance, jamais exposée à Internet.
- BeeDoo n'est pas un dispositif médical ni d'alerte : en cas de danger, appeler le 15 ou le 112.
