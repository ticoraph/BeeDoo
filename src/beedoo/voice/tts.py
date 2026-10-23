"""Synthèse vocale OpenAI (gpt-4o-mini-tts). Le texte est envoyé à OpenAI, voir DECISIONS.md.

Aucun contenu (texte, réponse d'erreur) n'est mis dans les messages d'erreur ni dans les logs :
un texte peut contenir un prénom, une réponse d'erreur peut citer ce texte.
"""

import json
import ssl
import urllib.error
import urllib.request

import certifi

from beedoo.config import Config
from beedoo.voice.pronunciation import to_spoken

URL = "https://api.openai.com/v1/audio/speech"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

CONSIGNE = ("Parle en français de France comme une petite fille de sept ans : voix aiguë, "
            "joyeuse, curieuse, un peu timide, ton enfantin et naturel, diction claire, {debit}.")


class TTSError(RuntimeError):
    """La synthèse a échoué (réseau, clé, quota). Le message ne contient jamais le texte."""


def consigne(vitesse: float) -> str:
    """La vitesse passe par la consigne de voix : le paramètre `speed` n'est pas garanti pour ce modèle."""
    debit = "débit lent" if vitesse < 0.85 else "débit rapide" if vitesse > 1.15 else "débit calme"
    return CONSIGNE.format(debit=debit)


def synthesize(config: Config, text: str, vitesse: float = 1.0, timeout: float = 30.0) -> bytes:
    """Audio MP3 du texte, avec la voix de BeeDoo."""
    if not config.openai_api_key:
        raise TTSError("clé OpenAI absente")
    body = {"model": config.tts_model, "voice": config.tts_voice, "input": to_spoken(text),
            "instructions": consigne(vitesse), "response_format": "mp3"}
    request = urllib.request.Request(
        URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {config.openai_api_key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise TTSError(f"OpenAI a répondu {error.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise TTSError(f"réseau indisponible ({type(error).__name__})") from None
