"""État partagé de l'application, lu et modifié par l'interface web et la boucle principale."""

import logging
import threading
from dataclasses import dataclass, field

from beedoo.config import Config
from beedoo.gestures.player import GesturePlayer
from beedoo.memory.store import MemoryStore
from beedoo.settings import Settings
from beedoo.state import State, StateMachine
from beedoo.tracking import HeadTracker
from beedoo.vision.enrollment import Enrollment
from beedoo.vision.faces import FaceStore
from beedoo.vision.greeter import Greeter
from beedoo.vision.loop import VisionLoop
from beedoo.voice.speaker import Speaker

log = logging.getLogger(__name__)


@dataclass
class Runtime:
    config: Config
    settings: Settings
    machine: StateMachine = field(default_factory=StateMachine)
    gestes: GesturePlayer | None = None  # None tant que le robot n'est pas connecté
    speaker: Speaker | None = None
    faces: FaceStore | None = None
    greeter: Greeter | None = None
    enrolement: Enrollment | None = None  # None sans caméra
    vision: VisionLoop | None = None
    suivi: HeadTracker | None = None
    memoire: MemoryStore | None = None
    miniapps: list = field(default_factory=list)  # mini-applications disponibles (miniapps.toutes())
    echange: dict | None = None  # dernière phrase entendue et dite, en mémoire seulement
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_muet(self, muet: bool) -> None:
        """Active ou coupe le mode muet, l'enregistre, et remet BeeDoo en veille si on le coupe."""
        with self._lock:
            self.settings.muet = muet
            self.settings.save(self.config.data_dir)
        if muet:
            self.machine.go(State.VEILLE)
        log.info("muet : %s", "oui" if muet else "non")

    def set_miniapp(self, nom: str, active: bool) -> None:
        """Active ou désactive une mini-application (KeyError si elle n'existe pas), et l'enregistre."""
        if nom not in {app.nom for app in self.miniapps}:
            raise KeyError(nom)
        with self._lock:
            coupees = set(self.settings.miniapps_desactivees)
            if active:
                coupees.discard(nom)
            else:
                coupees.add(nom)
            self.settings.miniapps_desactivees = sorted(coupees)
            self.settings.save(self.config.data_dir)

    def set_reglages(self, vitesse: float | None = None, voix: str | None = None,
                     suivi: bool | None = None, ville: str | None = None) -> None:
        """Change la vitesse, la voix, le suivi du visage et/ou la ville, et l'enregistre."""
        with self._lock:
            if ville is not None:
                self.settings.ville = ville
            if suivi is not None:
                self.settings.suivi = suivi
                if self.suivi is not None:
                    self.suivi.set_voulu(suivi)
            if vitesse is not None:
                self.settings.vitesse = vitesse
            if voix is not None:
                self.settings.voix = voix
            self.settings.clamp().save(self.config.data_dir)

    def status(self) -> dict:
        """Ce que l'interface affiche : jamais de clé, de transcription ni d'identité."""
        return {
            "etat": self.machine.state.value,
            "muet": self.settings.muet,
            "vitesse": self.settings.vitesse,
        }
