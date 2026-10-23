"""État partagé de l'application, lu et modifié par l'interface web et la boucle principale."""

import logging
import threading
from dataclasses import dataclass, field

from beedoo.config import Config
from beedoo.settings import Settings
from beedoo.state import State, StateMachine

log = logging.getLogger(__name__)


@dataclass
class Runtime:
    config: Config
    settings: Settings
    machine: StateMachine = field(default_factory=StateMachine)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_muet(self, muet: bool) -> None:
        """Active ou coupe le mode muet, l'enregistre, et remet BeeDoo en veille si on le coupe."""
        with self._lock:
            self.settings.muet = muet
            self.settings.save(self.config.data_dir)
        if muet:
            self.machine.go(State.VEILLE)
        log.info("muet : %s", "oui" if muet else "non")

    def status(self) -> dict:
        """Ce que l'interface affiche : jamais de clé, de transcription ni d'identité."""
        return {
            "etat": self.machine.state.value,
            "muet": self.settings.muet,
            "volume": self.settings.volume,
            "vitesse": self.settings.vitesse,
        }
