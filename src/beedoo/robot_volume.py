"""Volume du haut-parleur du robot, via l'API du daemon (source unique : on ne le recopie nulle part)."""

import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

TIMEOUT = 3.0


def _appel(url: str, donnees: dict | None = None) -> dict | None:
    requete = urllib.request.Request(
        url, data=None if donnees is None else json.dumps(donnees).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(requete, timeout=TIMEOUT) as reponse:
            return json.load(reponse)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as erreur:
        log.warning("volume : le daemon ne répond pas (%s)", type(erreur).__name__)
        return None


def lire(daemon_url: str) -> int | None:
    """Volume actuel (0 à 100), ou None si le daemon ne répond pas."""
    reponse = _appel(f"{daemon_url}/api/volume/current")
    return None if reponse is None else int(reponse["volume"])


def regler(daemon_url: str, volume: int) -> bool:
    """Règle le volume (0 à 100). False si le daemon ne répond pas."""
    if not 0 <= volume <= 100:
        raise ValueError("le volume va de 0 à 100")
    return _appel(f"{daemon_url}/api/volume/set", {"volume": volume}) is not None
