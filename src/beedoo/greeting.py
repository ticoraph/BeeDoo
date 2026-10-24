"""Salutation : quand la boucle de vision reconnaît quelqu'un, BeeDoo remue les antennes et dit bonjour.

Les logs ne contiennent pas le prénom (règle du dépôt : pas d'identité dans les logs).
"""

import json
import logging
import random
from pathlib import Path

from beedoo.runtime import Runtime
from beedoo.state import State
from beedoo.vision.greeter import SALUE, Event

log = logging.getLogger(__name__)

PHRASES = (
    "Bonjour {nom} !",
    "Coucou {nom} ! Je suis content de te voir.",
    "Salut {nom} ! Ça va ?",
    "Oh, {nom} ! Bonjour !",
)

FICHIER_PERSONNALISEES = "salutations.json"


def salutation_personnalisee(data_dir: Path, person: str) -> str | None:
    """Phrase de `data/salutations.json` pour cette personne (identifiant, ex. « lea »), sinon None.

    Le fichier est un objet JSON `{"identifiant": "phrase"}`. Il reste dans `data/` (donnée personnelle,
    jamais versionnée) et il est relu à chaque salutation : pas besoin de redémarrer après une modification.
    """
    try:
        contenu = json.loads((data_dir / FICHIER_PERSONNALISEES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    phrase = contenu.get(person) if isinstance(contenu, dict) else None
    return phrase.strip() if isinstance(phrase, str) and phrase.strip() else None


class Salutation:
    def __init__(self, runtime: Runtime, rng: random.Random | None = None) -> None:
        self._runtime = runtime
        self._rng = rng or random.Random()

    def on_event(self, event: Event) -> None:
        if event.kind != SALUE or not event.person:
            return  # visage inconnu : pour l'instant BeeDoo ne dit rien (enrôlement depuis l'interface)
        runtime = self._runtime
        avant = runtime.machine.state
        if avant not in (State.VEILLE, State.ECOUTE):
            return  # une phrase est en cours de traitement ou de parole : ne pas l'interrompre
        nom = runtime.faces.display_name(event.person)
        log.info("personne reconnue, salutation")
        if runtime.gestes is not None:
            runtime.gestes.play("antennes_content")
        if runtime.speaker is None:
            return
        try:
            runtime.machine.go(State.PAROLE)
        except ValueError:
            return
        try:
            phrase = salutation_personnalisee(runtime.config.data_dir, event.person)
            runtime.speaker.say(phrase or self._rng.choice(PHRASES).format(nom=nom))
        finally:
            try:
                runtime.machine.go(avant)
            except ValueError:  # le mode muet a remis BeeDoo en veille entre-temps
                pass
