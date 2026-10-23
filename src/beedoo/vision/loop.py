"""Boucle de vision : regarde la caméra environ une fois par seconde et prévient quand il faut saluer.

Les images restent en mémoire, ne sont jamais enregistrées ni envoyées. Une erreur d'analyse
(modèle absent, caméra muette) ne fait pas tomber l'application : la boucle ralentit et réessaie.
"""

import logging
import threading
from collections.abc import Callable

from beedoo.vision.greeter import Event, Greeter

log = logging.getLogger(__name__)

RALENTI = 5  # facteur de ralentissement après une erreur


class VisionLoop:
    def __init__(self, get_frame: Callable, identify: Callable, greeter: Greeter,
                 on_event: Callable[[Event], None], period: float = 1.0,
                 active: Callable[[], bool] = lambda: True) -> None:
        self._get_frame = get_frame
        self._identify = identify  # image -> Match (vision.faces)
        self._greeter = greeter
        self._on_event = on_event
        self._period = period
        self._active = active  # False = en pause (enrôlement en cours par exemple)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="beedoo-vision", daemon=True)
        self._erreurs = 0

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def step(self) -> Event | None:
        """Une analyse d'image. Renvoie l'événement déclenché, s'il y en a un."""
        frame = self._get_frame()
        if frame is None:
            return None
        match = self._identify(frame)
        if match.reason == "ambigu":  # entre deux personnes connues : ni inconnu, ni reconnu
            return None
        if match.reason == "aucun_visage":
            return self._greeter.observe(False)
        return self._greeter.observe(True, match.person)

    def _run(self) -> None:
        while not self._stop.is_set():
            attente = self._period
            if self._active():
                try:
                    event = self.step()
                    self._erreurs = 0
                    if event is not None:
                        self._on_event(event)
                except Exception as erreur:
                    # Peu de bruit dans les logs : on signale la 1re, 10e et 100e erreur de suite.
                    self._erreurs += 1
                    if self._erreurs in (1, 10, 100):
                        log.warning("analyse de l'image impossible (%d de suite, %s)", self._erreurs,
                                    type(erreur).__name__)
                    log.debug("détail de l'erreur d'analyse", exc_info=True)
                    attente = self._period * RALENTI
            self._stop.wait(attente)
