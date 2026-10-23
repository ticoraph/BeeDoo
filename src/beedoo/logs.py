"""Journalisation de BeeDoo.

Règle du dépôt : les logs ne contiennent ni clé API, ni transcription complète, ni identité,
seulement des identifiants techniques. Un filtre masque en plus tout ce qui ressemble à une clé,
au cas où l'une passerait dans un message d'erreur.
"""

import logging
import re
import threading
from collections import deque

CLE = re.compile(r"\b(?:sk|xi)-[A-Za-z0-9_\-]{8,}")
CHEMIN_PERSO = re.compile(r"/(?:Users|home)/[^/\s]+")
FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
MAX_MESSAGE = 300


class MasqueCles(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = CLE.sub("[clé masquée]", record.getMessage())
        record.args = None
        return True


def nettoyer(message: str) -> str:
    """Un message sûr à afficher dans la page : sans clé, sans chemin personnel, sur une ligne, borné."""
    message = CHEMIN_PERSO.sub("~", CLE.sub("[clé masquée]", message))
    message = " ".join(message.split())
    return message if len(message) <= MAX_MESSAGE else message[:MAX_MESSAGE - 1] + "…"


class JournalMemoire(logging.Handler):
    """Les événements récents, gardés en mémoire seulement (perdus à l'arrêt) pour la page « Journal ».

    Ne garde que les messages de BeeDoo (les bibliothèques sont bavardes) et, des autres, les avertissements.
    Jamais de trace d'exécution : elle peut citer des chemins ou des données.
    """

    def __init__(self, taille: int = 300) -> None:
        super().__init__(level=logging.INFO)
        self._lignes: deque[dict] = deque(maxlen=taille)
        self._numero = 0
        self._verrou = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        if not record.name.startswith("beedoo") and record.levelno < logging.WARNING:
            return
        with self._verrou:
            self._numero += 1
            self._lignes.append({
                "id": self._numero,
                "heure": self.formatter.formatTime(record, "%H:%M:%S") if self.formatter else "",
                "niveau": record.levelname,
                "source": record.name.rsplit(".", 1)[-1],
                "message": nettoyer(record.getMessage()),
            })

    def depuis(self, numero: int = 0, limite: int = 200) -> tuple[list[dict], int]:
        """Lignes plus récentes que `numero` (les plus anciennes d'abord) et le dernier numéro connu."""
        with self._verrou:
            if numero > self._numero:  # le journal a redémarré depuis : on repart du début
                numero = 0
            neuves = [dict(ligne) for ligne in self._lignes if ligne["id"] > numero]
            return neuves[-limite:], self._numero

    def vider(self) -> None:
        with self._verrou:
            self._lignes.clear()


JOURNAL = JournalMemoire()


def setup_logging(level: int = logging.INFO) -> None:
    """Configure la racine une seule fois (appel répété sans effet)."""
    racine = logging.getLogger()
    if any(isinstance(f, MasqueCles) for h in racine.handlers for f in h.filters):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT))
    handler.addFilter(MasqueCles())
    racine.addHandler(handler)
    JOURNAL.setFormatter(logging.Formatter(FORMAT))
    JOURNAL.addFilter(MasqueCles())
    racine.addHandler(JOURNAL)
    racine.setLevel(level)
