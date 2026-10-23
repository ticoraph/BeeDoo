"""Salutation : quand la boucle de vision reconnaît quelqu'un, BeeDoo remue les antennes et dit bonjour.

Les logs ne contiennent pas le prénom (règle du dépôt : pas d'identité dans les logs).
"""

import logging
import random

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
            runtime.speaker.say(self._rng.choice(PHRASES).format(nom=nom))
        finally:
            try:
                runtime.machine.go(avant)
            except ValueError:  # le mode muet a remis BeeDoo en veille entre-temps
                pass
