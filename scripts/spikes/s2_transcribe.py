"""Essai S2 : transcription des phrases enregistrées par s4_listen.py avec gpt-4o-transcribe.

    python scripts/spikes/s2_transcribe.py [dossier]

Par défaut : data/spikes/utterances/*.wav (ignoré par git, ce sont des voix). Chaque fichier est envoyé
à OpenAI (voir DECISIONS.md : D1 et « Données envoyées hors du Mac »). Les textes sont écrits à côté
des sons (.txt), jamais dans un fichier versionné.
"""

import json
import ssl
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import certifi

from beedoo.config import REPO_ROOT, Config

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
URL = "https://api.openai.com/v1/audio/transcriptions"


def transcribe(config: Config, wav: Path) -> str:
    boundary = uuid.uuid4().hex
    fields = {"model": config.stt_model, "language": "fr", "response_format": "json"}
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields.items()
    ]
    parts.append(
        (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{wav.name}"\r\n'
         "Content-Type: audio/wav\r\n\r\n").encode() + wav.read_bytes() + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        URL,
        data=b"".join(parts),
        headers={
            "Authorization": f"Bearer {config.openai_api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(request, context=SSL_CONTEXT, timeout=60) as response:
        return json.load(response)["text"]


def main() -> None:
    config = Config.load()
    if config.missing_keys():
        sys.exit(f"Clé manquante dans .env : {', '.join(config.missing_keys())}")
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "data" / "spikes" / "utterances"
    for wav in sorted(folder.glob("*.wav"), key=lambda p: (len(p.stem), p.stem)):
        start = time.time()
        text = transcribe(config, wav)
        wav.with_suffix(".txt").write_text(text + "\n", encoding="utf-8")
        print(f"{wav.name} ({time.time() - start:.1f} s) : {text}")


if __name__ == "__main__":
    main()
