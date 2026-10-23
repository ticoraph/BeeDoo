"""Journalisation de BeeDoo.

Règle du dépôt : les logs ne contiennent ni clé API, ni transcription complète, ni identité,
seulement des identifiants techniques. Un filtre masque en plus tout ce qui ressemble à une clé,
au cas où l'une passerait dans un message d'erreur.
"""

import logging
import re

CLE = re.compile(r"\b(?:sk|xi)-[A-Za-z0-9_\-]{8,}")
FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class MasqueCles(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = CLE.sub("[clé masquée]", record.getMessage())
        record.args = None
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """Configure la racine une seule fois (appel répété sans effet)."""
    racine = logging.getLogger()
    if any(isinstance(f, MasqueCles) for h in racine.handlers for f in h.filters):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT))
    handler.addFilter(MasqueCles())
    racine.addHandler(handler)
    racine.setLevel(level)
