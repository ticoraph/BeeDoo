"""Reconnaissance vocale OpenAI (gpt-4o-transcribe). L'audio est envoyé à OpenAI, voir DECISIONS.md.

Comme pour la synthèse : aucun contenu (audio, texte, réponse d'erreur) dans les messages d'erreur ni
les logs. Sur du bruit, le modèle invente parfois du texte (essai S2 : « 嘶嘶嘶 », « あー »,
« Sous-titres… ») : `plausible()` écarte ces sorties.
"""

import io
import json
import ssl
import unicodedata
import urllib.error
import urllib.request
import uuid
import wave

import certifi
import numpy as np

from beedoo.config import Config
from beedoo.voice.pronunciation import normalize_heard_name

URL = "https://api.openai.com/v1/audio/transcriptions"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Phrases que le modèle invente sur du silence ou du bruit (vidéos sous-titrées dans ses données).
INVENTEES = ("sous-titr", "amara.org", "merci d'avoir regardé", "merci d’avoir regardé",
             "abonnez-vous", "n'oubliez pas de vous abonner")


class STTError(RuntimeError):
    """La transcription a échoué (réseau, clé, quota). Le message ne contient jamais l'audio ni le texte."""


def to_wav(audio: np.ndarray, samplerate: int) -> bytes:
    """Audio mono flottant (-1 à 1) en WAV 16 bits, en mémoire : rien n'est écrit sur le disque."""
    pcm = (np.clip(np.asarray(audio, dtype=np.float32), -1, 1) * 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(samplerate)
        f.writeframes(pcm.tobytes())
    return buffer.getvalue()


def plausible(text: str) -> bool:
    """Faux pour un texte vide, en écriture non latine, ou qui ressemble à une invention du modèle."""
    text = text.strip()
    lettres = [c for c in text if c.isalpha()]
    if len(lettres) < 2:
        return False
    latines = sum("LATIN" in unicodedata.name(c, "") for c in lettres)
    if latines / len(lettres) < 0.9:
        return False
    bas = text.lower()
    return not any(phrase in bas for phrase in INVENTEES)


def transcribe_wav(config: Config, wav: bytes, nom: str = "phrase.wav", timeout: float = 60.0) -> str:
    """Texte d'un fichier WAV, en français."""
    if not config.openai_api_key:
        raise STTError("clé OpenAI absente")
    frontiere = uuid.uuid4().hex
    champs = {"model": config.stt_model, "language": "fr", "response_format": "json"}
    parts = [f'--{frontiere}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
             for k, v in champs.items()]
    parts.append((f'--{frontiere}\r\nContent-Disposition: form-data; name="file"; filename="{nom}"\r\n'
                  "Content-Type: audio/wav\r\n\r\n").encode() + wav + b"\r\n")
    parts.append(f"--{frontiere}--\r\n".encode())
    request = urllib.request.Request(
        URL, data=b"".join(parts),
        headers={"Authorization": f"Bearer {config.openai_api_key}",
                 "Content-Type": f"multipart/form-data; boundary={frontiere}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
            return json.load(response)["text"]
    except urllib.error.HTTPError as error:
        raise STTError(f"OpenAI a répondu {error.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as error:
        raise STTError(f"transcription impossible ({type(error).__name__})") from None


def transcribe(config: Config, audio: np.ndarray, samplerate: int) -> str:
    """Texte de la phrase (le nom « BeeDoo » est normalisé), éventuellement vide ou invraisemblable."""
    return normalize_heard_name(transcribe_wav(config, to_wav(audio, samplerate)).strip())
