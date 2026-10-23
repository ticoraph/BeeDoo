"""Mini-applications déclenchées par mots-clés (phase 6) : blague Toto, météo, heure et date.

Pour en ajouter une : écrire une classe `MiniApp` (voir `base.py`) dans un nouveau fichier de ce dossier,
puis l'ajouter à `toutes()`. Les actualités ne sont pas prévues pour l'instant (décision du 2026-10-23).
"""

from beedoo.miniapps.base import MiniApp
from beedoo.miniapps.heure import HeureDate
from beedoo.miniapps.meteo import Meteo
from beedoo.miniapps.toto import Toto


def toutes() -> list[MiniApp]:
    """Les mini-applications disponibles, dans l'ordre où leurs mots-clés sont essayés."""
    return [Toto(), Meteo(), HeureDate()]
