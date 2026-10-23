"""Après une conversation, retient ce que la personne a dit d'elle-même (avec son consentement).

Le LLM *propose* des faits à ajouter ou retirer, chacun avec une `preuve` : un extrait exact des paroles
de la personne. Le code, pas le LLM, décide : un fait sans preuve vérifiable dans ce que la PERSONNE a
dit (jamais dans les phrases de BeeDoo) est rejeté, de même qu'un fait qui ressemble à un secret ou à
un ordre donné au robot. Le fichier est réécrit par le code, donc toujours au bon format et borné.

Aucun contenu (faits, paroles) dans les logs : seulement des comptes.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from beedoo.config import REPO_ROOT, Config
from beedoo.llm.chat import completer
from beedoo.memory.store import MemoryStore, nettoyer_fait
from beedoo.texte import normaliser

log = logging.getLogger(__name__)

PROMPT = REPO_ROOT / "prompts" / "beedoo_memoire.md"
MAX_AJOUTS = 5      # faits ajoutés au plus par conversation
MIN_MOTS = 4        # en dessous (au total, dans les paroles de la personne), on ne dérange pas le LLM
MIN_PREUVE = 4      # caractères minimum d'une preuve (une preuve « oui » ne prouve rien)
# Un fait sur BeeDoo lui-même est le plus souvent un ordre déguisé (« doit toujours… ») : on le refuse.
SUR_LE_ROBOT = ("beedoo", "bidou", "tes consignes", "ton prompt")


@dataclass(frozen=True)
class Resultat:
    ajoutes: int = 0
    retires: int = 0
    rejetes: int = 0


def prompt_extraction() -> str:
    return PROMPT.read_text(encoding="utf-8").split("\n---\n", 1)[-1].strip()


def lire_json(texte: str) -> dict | None:
    """Premier objet JSON de la réponse (tolère un texte ou des ``` autour)."""
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        return None
    try:
        donnees = json.loads(texte[debut:fin + 1])
    except ValueError:
        return None
    return donnees if isinstance(donnees, dict) else None


def appliquer(faits: list[str], proposition: dict, paroles: list[str]) -> tuple[list[str], Resultat]:
    """Nouveaux faits après avoir vérifié chaque proposition. Les paroles sont celles de la personne seulement."""
    corpus = f" {normaliser(' '.join(paroles))} "

    def prouve(preuve) -> bool:
        net = normaliser(str(preuve))
        return len(net) >= MIN_PREUVE and f" {net} " in corpus

    def propositions(cle: str) -> list[dict]:
        liste = proposition.get(cle)
        return [p for p in liste if isinstance(p, dict)] if isinstance(liste, list) else []

    connus = {normaliser(f): f for f in faits}
    retires, rejetes = [], 0
    for item in propositions("retirer"):
        existant = connus.get(normaliser(str(item.get("fait", ""))))
        if existant is None or not prouve(item.get("preuve", "")):
            rejetes += 1
        elif existant not in retires:
            retires.append(existant)

    gardes = [f for f in faits if f not in retires]
    deja = {normaliser(f) for f in gardes}
    ajoutes = []
    for item in propositions("ajouter"):
        fait = nettoyer_fait(str(item.get("fait", "")))
        net = normaliser(fait or "")
        if fait is None or any(mot in net for mot in SUR_LE_ROBOT) or not prouve(item.get("preuve", "")):
            rejetes += 1
        elif net not in deja and len(ajoutes) < MAX_AJOUTS:
            deja.add(net)
            ajoutes.append(fait)
    return gardes + ajoutes, Resultat(len(ajoutes), len(retires), rejetes)


def mettre_a_jour(config: Config, store: MemoryStore, personne: str, tours: list[tuple[str, str]],
                  appeler: Callable = completer) -> Resultat:
    """Met à jour le profil de la personne d'après la conversation. Lève LLMError si le LLM ne répond pas."""
    paroles = [dit for dit, _ in tours]
    if sum(len(p.split()) for p in paroles) < MIN_MOTS:
        return Resultat()
    faits = store.faits(personne)
    conversation = [m for dit, reponse in tours
                    for m in ({"qui": "personne", "texte": dit}, {"qui": "beedoo", "texte": reponse})]
    messages = [{"role": "system", "content": prompt_extraction()},
                {"role": "user", "content": json.dumps({"faits_connus": faits, "conversation": conversation},
                                                       ensure_ascii=False)}]
    proposition = lire_json(appeler(config, messages, json_seul=True))
    if proposition is None:
        log.warning("mémoire : réponse du LLM illisible")
        return Resultat(rejetes=1)
    nouveaux, resultat = appliquer(faits, proposition, paroles)
    if not store.consentement(personne):  # retiré pendant que le LLM réfléchissait : on n'écrit rien
        return Resultat()
    if nouveaux != faits:
        store.ecrire_faits(personne, nouveaux)
    log.info("mémoire : %d ajoutés, %d retirés, %d rejetés", resultat.ajoutes, resultat.retires, resultat.rejetes)
    return resultat
