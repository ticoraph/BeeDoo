"""Configuration de BeeDoo.

Les secrets viennent de `.env` (jamais versionné), les données personnelles
vivent dans `data/` (jamais versionné non plus). Voir `.env.example`.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    """Réglages lus dans l'environnement. La clé n'apparaît jamais dans repr()."""

    data_dir: Path
    openai_model: str
    stt_model: str
    tts_model: str
    tts_voice: str
    openai_api_key: str = field(default="", repr=False)

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Config":
        load_dotenv(env_file or REPO_ROOT / ".env")
        return cls(
            data_dir=Path(os.environ.get("BEEDOO_DATA_DIR") or REPO_ROOT / "data"),
            openai_model=os.environ.get("OPENAI_MODEL") or "gpt-6-luna",
            stt_model=os.environ.get("OPENAI_STT_MODEL") or "gpt-4o-transcribe",
            tts_model=os.environ.get("OPENAI_TTS_MODEL") or "gpt-4o-mini-tts",
            tts_voice=os.environ.get("OPENAI_TTS_VOICE") or "fable",
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        )

    def missing_keys(self) -> list[str]:
        """Noms des variables d'environnement obligatoires qui sont vides."""
        return [] if self.openai_api_key else ["OPENAI_API_KEY"]
