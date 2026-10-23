"""Cadre des mini-applications : de quoi en écrire une nouvelle en peu de temps.

Une mini-application est une classe `MiniApp` avec :
- des mots-clés « sûrs » (on la lance tout de suite) et « vagues » (BeeDoo demande d'abord confirmation) ;
- une phrase de proposition (pour la confirmation) et une phrase de présentation ;
- une méthode `repondre()` qui renvoie ce que BeeDoo dit.

On l'ajoute ensuite à la liste `TOUTES` de `beedoo/miniapps/__init__.py`. Rien d'autre à brancher.
"""

import re
import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

from beedoo.miniapps.http import get_json
from beedoo.settings import Settings


def normaliser(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation, espaces simples : « Quel TEMPS, demain ? » -> « quel temps demain »."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).split())


def contient(texte_normalise: str, mots: tuple[str, ...]) -> bool:
    """Vrai si l'un des mots ou groupes de mots est dans le texte, en mots entiers (« rire » pas dans « sourire »)."""
    entoure = f" {texte_normalise} "
    return any(f" {normaliser(mot)} " in entoure for mot in mots)


@dataclass(frozen=True)
class Reponse:
    """Ce que BeeDoo dit : une ou plusieurs parties dites l'une après l'autre (pause entre deux)."""

    parties: tuple[str, ...]
    geste: str | None = None  # geste joué avec la dernière partie (voir gestures/library.py)


@dataclass
class Contexte:
    settings: Settings
    prenom: str = "inconnu"
    http_json: Callable[[str], dict] = field(default=get_json)  # remplaçable dans les tests


class MiniApp(ABC):
    nom: str                         # identifiant court et stable (réglages), ex. « toto »
    titre: str                       # nom affiché dans l'interface
    mots_surs: tuple[str, ...]       # lancent la mini-app tout de suite
    mots_vagues: tuple[str, ...] = ()  # BeeDoo demande d'abord « proposition »
    proposition: str                 # ex. « Tu veux que je te raconte une blague ? »

    @abstractmethod
    def repondre(self, texte: str, contexte: Contexte) -> Reponse:
        """`texte` est la phrase entendue, normalisée (voir `normaliser`)."""
