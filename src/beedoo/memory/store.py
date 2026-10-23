"""Mémoire par personne, en fichiers texte dans `data/personnes/<id>/` (jamais versionné).

    memoire.json                   consentement de la personne (éteint tant qu'on ne l'a pas coché)
    profil.md                      les faits retenus, une ligne « - … » par fait (modifiable à la main)
    conversations/AAAA-MM-JJ_HHMM.md   les conversations complètes

Sans consentement, rien n'est lu ni écrit : `souvenirs()` répond « rien pour l'instant » et
`enregistrer_conversation()` ne fait rien. Effacer une personne (`FaceStore.forget`) supprime tout son
dossier, mémoire comprise. Aucun contenu n'est jamais mis dans les logs.
"""

import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from beedoo.vision.faces import person_id

log = logging.getLogger(__name__)

MAX_FAITS = 30      # au-delà, les plus anciens sont oubliés
MAX_FAIT = 140      # caractères par fait
RIEN = "rien pour l'instant"

# Ce qu'on ne garde jamais, même si la personne le dit : numéros longs (téléphone, carte), adresses
# électroniques, liens, mots de passe et codes.
INTERDIT = re.compile(
    r"\d(?:[\s.\-]?\d){5,}|@|https?:|www\.|mot de passe|mots de passe|code secret|code pin|\biban\b|\bcvv?\b",
    re.IGNORECASE)


def nettoyer_fait(texte: str) -> str | None:
    """Fait prêt à être gardé (une ligne, 3 à 140 caractères), ou None s'il est inacceptable."""
    fait = " ".join(texte.replace("\n", " ").split()).removeprefix("- ").strip()
    if not 3 <= len(fait) <= MAX_FAIT or INTERDIT.search(fait):
        return None
    return fait


def _ecrire(chemin: Path, contenu: str) -> None:
    """Écriture atomique, lisible par l'utilisateur seul."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_name(chemin.name + ".tmp")
    tmp.write_text(contenu, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, chemin)


class MemoryStore:
    def __init__(self, data_dir: Path) -> None:
        self.root = Path(data_dir) / "personnes"

    def _dossier(self, personne: str) -> Path:
        return self.root / person_id(personne)

    # --- consentement ------------------------------------------------------------------------
    def consentement(self, personne: str) -> bool:
        try:
            return json.loads((self._dossier(personne) / "memoire.json").read_text())["consentement"] is True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def set_consentement(self, personne: str, accepte: bool) -> None:
        _ecrire(self._dossier(personne) / "memoire.json", json.dumps({"consentement": bool(accepte)}))

    # --- faits --------------------------------------------------------------------------------
    def faits(self, personne: str) -> list[str]:
        """Les faits gardés (même sans consentement : c'est ce qui est sur le disque, pour l'afficher ou l'effacer)."""
        try:
            lignes = (self._dossier(personne) / "profil.md").read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        return [f for f in (nettoyer_fait(ligne) for ligne in lignes if ligne.startswith("- ")) if f]

    def ecrire_faits(self, personne: str, faits: list[str]) -> list[str]:
        """Remplace le profil (les plus récents d'abord gardés au-delà de MAX_FAITS). Renvoie ce qui est écrit.

        Lève ValueError si un fait est inacceptable. L'ancienne version est gardée dans profil.md.bak.
        """
        propres = []
        for fait in faits:
            net = nettoyer_fait(fait)
            if net is None:
                raise ValueError("fait refusé")
            if net not in propres:
                propres.append(net)
        propres = propres[-MAX_FAITS:]
        fichier = self._dossier(personne) / "profil.md"
        if fichier.exists():
            shutil.copy2(fichier, fichier.with_name("profil.md.bak"))
        _ecrire(fichier, "".join(f"- {fait}\n" for fait in propres))
        return propres

    def souvenirs(self, personne: str | None) -> str:
        """Ce qui va dans `{{souvenirs}}` du prompt : les faits de CETTE personne seulement, et seulement
        avec son consentement."""
        if not personne or not self.consentement(personne):
            return RIEN
        faits = self.faits(personne)
        return "\n".join(f"- {f}" for f in faits) if faits else RIEN

    # --- conversations ------------------------------------------------------------------------
    def enregistrer_conversation(self, personne: str, nom: str, tours: list[tuple[str, str]],
                                 debut: datetime) -> Path | None:
        """Écrit la conversation (paroles de la personne, réponses de BeeDoo). None sans consentement ni tour."""
        if not tours or not self.consentement(personne):
            return None
        dossier = self._dossier(personne) / "conversations"
        base = debut.strftime("%Y-%m-%d_%H%M")
        chemin, n = dossier / f"{base}.md", 2
        while chemin.exists():
            chemin, n = dossier / f"{base}_{n}.md", n + 1
        lignes = [f"# Conversation du {debut.strftime('%Y-%m-%d à %H:%M')}", ""]
        for dit, reponse in tours:
            lignes += [f"**{nom}** : {dit}", f"**BeeDoo** : {reponse}", ""]
        _ecrire(chemin, "\n".join(lignes))
        return chemin

    def conversations(self, personne: str) -> list[str]:
        dossier = self._dossier(personne) / "conversations"
        return sorted(p.stem for p in dossier.glob("*.md")) if dossier.is_dir() else []

    # --- effacement ---------------------------------------------------------------------------
    def effacer(self, personne: str) -> None:
        """Efface les souvenirs (faits, copie de sauvegarde, conversations). Garde le visage et le consentement."""
        dossier = self._dossier(personne)
        for nom in ("profil.md", "profil.md.bak"):
            (dossier / nom).unlink(missing_ok=True)
        shutil.rmtree(dossier / "conversations", ignore_errors=True)
