"""Réglages modifiables de BeeDoo, stockés dans `data/settings.json` (jamais versionné).

Les valeurs par défaut sont sûres : un fichier absent, illisible ou aux valeurs hors limites
ne fait jamais planter l'application. Les clés API ne passent pas ici (elles sont dans `.env`).
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

log = logging.getLogger(__name__)

SETTINGS_FILE = "settings.json"

# Voix OpenAI essayées en S1 (voir DECISIONS.md D1) ; `fable` est la voix par défaut du projet.
VOIX = ("fable", "coral", "shimmer", "nova", "marin")


@dataclass
class Settings:
    muet: bool = False
    vitesse: float = 1.0  # vitesse de la voix, 0,5 à 1,5
    suivi: bool = True  # la tête suit le visage de la personne
    ville: str = ""  # pour la météo ; envoyée à Open-Meteo (voir DECISIONS.md)
    miniapps_desactivees: list[str] = field(default_factory=list)
    voix: str = ""  # voix OpenAI choisie dans l'interface ; vide = celle de la configuration (.env)

    def clamp(self) -> "Settings":
        """Ramène chaque valeur dans ses limites (modifie l'objet et le renvoie)."""
        self.vitesse = min(1.5, max(0.5, float(self.vitesse)))
        self.muet = bool(self.muet)
        self.suivi = bool(self.suivi)
        self.ville = " ".join(str(self.ville).split())[:80]
        coupees = self.miniapps_desactivees if isinstance(self.miniapps_desactivees, list) else []
        self.miniapps_desactivees = sorted({str(nom) for nom in coupees})
        self.voix = self.voix if self.voix in VOIX else ""
        return self

    @classmethod
    def load(cls, data_dir: Path) -> "Settings":
        path = data_dir / SETTINGS_FILE
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("le fichier doit contenir un objet JSON")
            known = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in raw.items() if k in known}).clamp()
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError, TypeError) as error:
            # Le message ne cite pas le contenu du fichier, seulement la nature de l'erreur.
            log.warning("réglages illisibles (%s), valeurs par défaut", type(error).__name__)
            return cls()

    def save(self, data_dir: Path) -> None:
        """Écriture atomique : un arrêt en plein milieu ne laisse pas un fichier à moitié écrit."""
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / SETTINGS_FILE
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(self.clamp()), indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
