"""Petit client HTTP pour les mini-applications (JSON, certificats vérifiés, délai court)."""

import json
import ssl
import urllib.request

import certifi

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class ReseauIndisponible(RuntimeError):
    """Le service n'a pas répondu. Le message ne contient jamais l'adresse (elle peut citer une ville)."""


def get_json(url: str, timeout: float = 8.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=SSL_CONTEXT) as reponse:
            return json.load(reponse)
    except (OSError, ValueError) as erreur:
        raise ReseauIndisponible(type(erreur).__name__) from None
