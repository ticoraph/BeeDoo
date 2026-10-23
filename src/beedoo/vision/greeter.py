"""Décide quand BeeDoo salue : une fois par arrivée, jamais en boucle.

Pure logique, sans caméra ni DeepFace : on lui donne le résultat de chaque analyse d'image et il dit
s'il faut réagir. Règles :
- une personne doit être reconnue sur `confirmations` analyses de suite avant d'être saluée
  (une seule image peut se tromper) ;
- une personne déjà saluée n'est resaluée que si `delai_salut` s'est écoulé depuis le dernier salut
  ET qu'elle est restée hors de vue au moins `absence` secondes (elle est partie puis revenue) ;
- un visage inconnu est signalé une seule fois par présence, jusqu'à `absence` secondes sans visage.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

SALUE = "salue"
INCONNU = "inconnu"


@dataclass(frozen=True)
class Event:
    kind: str  # SALUE ou INCONNU
    person: str | None = None


class Greeter:
    def __init__(self, confirmations: int = 2, delai_salut: float = 600.0, absence: float = 20.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if confirmations < 1:
            raise ValueError("confirmations doit être au moins 1")
        self.confirmations = confirmations
        self.delai_salut = delai_salut
        self.absence = absence
        self._clock = clock
        self._candidate: str | None = None  # personne, ou "" pour un visage inconnu
        self._count = 0
        self._last_seen: dict[str, float] = {}
        self._last_greeted: dict[str, float] = {}
        self._last_face = float("-inf")
        self._unknown_signaled = False

    def observe(self, face_seen: bool, person: str | None = None) -> Event | None:
        """Résultat d'une analyse : visage vu ou non, et la personne reconnue (None = inconnue)."""
        now = self._clock()
        if not face_seen:
            self._candidate, self._count = None, 0
            if now - self._last_face >= self.absence:
                self._unknown_signaled = False
            return None

        self._last_face = now
        key = person or ""
        self._count = self._count + 1 if key == self._candidate else 1
        self._candidate = key
        if self._count < self.confirmations:
            return None

        if not person:
            if self._unknown_signaled:
                return None
            self._unknown_signaled = True
            return Event(INCONNU)

        absent_depuis = now - self._last_seen.get(person, float("-inf"))
        self._last_seen[person] = now
        deja_salue = person in self._last_greeted
        if deja_salue and not (now - self._last_greeted[person] >= self.delai_salut
                               and absent_depuis >= self.absence):
            return None
        self._last_greeted[person] = now
        return Event(SALUE, person)

    def forget(self, person: str) -> None:
        """Oublie une personne effacée : si elle revient, elle sera traitée comme nouvelle."""
        self._last_seen.pop(person, None)
        self._last_greeted.pop(person, None)
