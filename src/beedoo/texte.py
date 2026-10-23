"""Petits outils sur le texte, partagés (mini-applications, mémoire)."""

import re
import unicodedata


def normaliser(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation, espaces simples : « Quel TEMPS, demain ? » -> « quel temps demain »."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).split())
