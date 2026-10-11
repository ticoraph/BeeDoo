"""Prononciation du nom de BeeDoo.

La synthèse vocale lit « BeeDoo » à l'anglaise ou de travers, et la reconnaissance
vocale entend plutôt « Bidou » ou « Didou ». On écrit donc le nom phonétiquement
avant de le faire lire, et on accepte les variantes en entrée.
"""

import re

SPOKEN_NAME = "Bidou"
NAME = "BeeDoo"

_WRITTEN = re.compile(r"\bbee[\s-]?doo\b", re.IGNORECASE)
_HEARD = re.compile(r"\b(bee[\s-]?doo|bi[\s-]?dou[x]?|di[\s-]?dou[x]?)\b", re.IGNORECASE)


def to_spoken(text: str) -> str:
    """Texte à donner à la synthèse vocale : le nom est écrit comme on le prononce."""
    return _WRITTEN.sub(SPOKEN_NAME, text)


def normalize_heard_name(text: str) -> str:
    """Texte transcrit : toutes les variantes du nom deviennent « BeeDoo »."""
    return _HEARD.sub(NAME, text)
