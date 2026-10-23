"""Essai S2 : transcription des phrases enregistrées par s4_listen.py avec gpt-4o-transcribe.

    python scripts/spikes/s2_transcribe.py [dossier]

Par défaut : data/spikes/utterances/*.wav (ignoré par git, ce sont des voix). Chaque fichier est envoyé
à OpenAI (voir DECISIONS.md : D1 et « Données envoyées hors du Mac »). Les textes sont écrits à côté
des sons (.txt), jamais dans un fichier versionné.
"""

import sys
import time
from pathlib import Path

from beedoo.config import REPO_ROOT, Config
from beedoo.voice.stt import transcribe_wav


def transcribe(config: Config, wav: Path) -> str:
    return transcribe_wav(config, wav.read_bytes(), wav.name)


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
