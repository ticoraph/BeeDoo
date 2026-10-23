"""Fait parler BeeDoo par le haut-parleur du robot : synthèse, lecture, attente de la fin.

Un seul texte à la fois. En mode muet, BeeDoo ne parle pas. Le fichier audio temporaire est effacé
après lecture : les paroles de BeeDoo ne sont pas conservées.
"""

import logging
import os
import tempfile
import threading

from beedoo.config import Config
from beedoo.settings import Settings
from beedoo.voice.tts import TTSError, synthesize

log = logging.getLogger(__name__)

MARGE = 0.3  # secondes d'attente en plus de la durée du son


class Speaker:
    def __init__(self, mini, config: Config, settings: Settings) -> None:
        self._mini = mini
        self._config = config
        self._settings = settings  # objet partagé : le bouton muet agit tout de suite
        self._verrou = threading.Lock()
        self._interrompu = threading.Event()

    @property
    def parle(self) -> bool:
        return self._verrou.locked()

    def say(self, text: str) -> bool:
        """Dit le texte et attend la fin. False si rien n'a été dit (muet, déjà en train de parler, erreur)."""
        if self._settings.muet or not self._verrou.acquire(blocking=False):
            return False
        self._interrompu.clear()
        chemin = None
        try:
            audio = synthesize(self._config, text, self._settings.vitesse, self._settings.voix or None)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fichier:
                fichier.write(audio)
                chemin = fichier.name
            from reachy_mini.media.gstreamer_utils import audio_duration_seconds

            duree = audio_duration_seconds(chemin)
            self._mini.media.play_sound(chemin)
            self._interrompu.wait(duree + MARGE)
            return not self._interrompu.is_set()
        except TTSError as erreur:
            log.warning("BeeDoo n'a pas pu parler : %s", erreur)
            return False
        except Exception:
            log.exception("BeeDoo n'a pas pu parler (erreur de lecture)")
            return False
        finally:
            if chemin:
                try:
                    os.unlink(chemin)
                except OSError:
                    pass
            self._verrou.release()

    def stop(self) -> None:
        """Coupe la parole en cours."""
        self._interrompu.set()
        try:
            self._mini.media.audio.clear_player()
        except Exception:
            log.debug("clear_player indisponible")
