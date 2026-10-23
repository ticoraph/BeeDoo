"""États de BeeDoo : veille, écoute, réflexion, parole.

Une seule personne à la fois, un seul état à la fois. Les transitions permises sont explicites :
une transition inattendue est un bogue et lève une erreur plutôt que de passer inaperçue.
"""

import logging
import threading
from collections.abc import Callable
from enum import Enum

log = logging.getLogger(__name__)


class State(Enum):
    VEILLE = "veille"
    ECOUTE = "écoute"
    REFLEXION = "réflexion"
    PAROLE = "parole"


# Depuis un état, on peut toujours revenir à la veille (arrêt, bouton muet, erreur).
TRANSITIONS: dict[State, set[State]] = {
    State.VEILLE: {State.ECOUTE, State.PAROLE},  # PAROLE : salutation spontanée
    State.ECOUTE: {State.REFLEXION, State.VEILLE},
    State.REFLEXION: {State.PAROLE, State.VEILLE},
    State.PAROLE: {State.ECOUTE, State.VEILLE},
}


class StateMachine:
    def __init__(self) -> None:
        self._state = State.VEILLE
        self._lock = threading.Lock()
        self._listeners: list[Callable[[State, State], None]] = []

    @property
    def state(self) -> State:
        return self._state

    def on_change(self, listener: Callable[[State, State], None]) -> None:
        """`listener(ancien, nouveau)` est appelé après chaque changement d'état."""
        self._listeners.append(listener)

    def go(self, new: State) -> None:
        with self._lock:
            old = self._state
            if new == old:
                return
            if new not in TRANSITIONS[old]:
                raise ValueError(f"transition interdite : {old.value} -> {new.value}")
            self._state = new
        log.info("état : %s -> %s", old.value, new.value)
        for listener in self._listeners:
            listener(old, new)
