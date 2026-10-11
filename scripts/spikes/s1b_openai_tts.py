"""Essai S1b : voix d'enfant avec OpenAI gpt-4o-mini-tts (alternative à ElevenLabs).

    python scripts/spikes/s1b_openai_tts.py

Génère la même phrase avec plusieurs voix, enregistrées dans data/spikes/ (ignoré par git),
et affiche le temps de génération. À écouter : open data/spikes/openai_tts_*.mp3
"""

import json
import ssl
import time
import urllib.request

import certifi

from beedoo.config import REPO_ROOT, Config

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
TEXT = "Bonjour ! Je suis BeeDoo, un petit robot. Je suis très content de te voir. Tu veux que je te raconte une blague ?"
INSTRUCTIONS = ("Parle en français de France comme une petite fille de sept ans : voix aiguë, "
                "joyeuse, curieuse, un peu timide, ton enfantin et naturel, diction claire, débit calme.")
VOICES = ["coral", "shimmer", "nova", "fable", "marin"]


def main() -> None:
    config = Config.load()
    out_dir = REPO_ROOT / "data" / "spikes"
    out_dir.mkdir(parents=True, exist_ok=True)
    for voice in VOICES:
        body = {"model": "gpt-4o-mini-tts", "voice": voice, "input": TEXT,
                "instructions": INSTRUCTIONS, "response_format": "mp3"}
        request = urllib.request.Request(
            "https://api.openai.com/v1/audio/speech", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {config.openai_api_key}", "Content-Type": "application/json"})
        start = time.time()
        try:
            with urllib.request.urlopen(request, timeout=90, context=SSL_CONTEXT) as response:
                audio = response.read()
        except urllib.error.HTTPError as error:
            print(f"{voice}: erreur {error.code} {error.read().decode()[:200]}")
            continue
        path = out_dir / f"openai_tts_{voice}.mp3"
        path.write_bytes(audio)
        print(f"{voice}: {len(audio) // 1024} Ko en {time.time() - start:.1f}s -> {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
