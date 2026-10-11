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
    """Réglages lus dans l'environnement. Les clés n'apparaissent jamais dans repr()."""

    data_dir: Path
    openai_model: str
    openai_api_key: str = field(default="", repr=False)
    elevenlabs_api_key: str = field(default="", repr=False)
    elevenlabs_voice_id: str = ""

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Config":
        load_dotenv(env_file or REPO_ROOT / ".env")
        return cls(
            data_dir=Path(os.environ.get("BEEDOO_DATA_DIR") or REPO_ROOT / "data"),
            openai_model=os.environ.get("OPENAI_MODEL") or "gpt-6-luna",
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            elevenlabs_api_key=os.environ.get("ELEVENLABS_API_KEY", ""),
            elevenlabs_voice_id=os.environ.get("ELEVENLABS_VOICE_ID", ""),
        )

    def missing_keys(self) -> list[str]:
        """Noms des variables d'environnement obligatoires qui sont vides."""
        required = {
            "OPENAI_API_KEY": self.openai_api_key,
            "ELEVENLABS_API_KEY": self.elevenlabs_api_key,
            "ELEVENLABS_VOICE_ID": self.elevenlabs_voice_id,
        }
        return [name for name, value in required.items() if not value]
