"""Enrôlement d'une personne par la caméra : quelques images à quelques secondes d'intervalle.

On ne garde que les empreintes (jamais les images). La personne est invitée à tourner doucement la
tête entre deux prises, pour que l'empreinte couvre plusieurs poses (voir l'essai S3).
"""

import logging
import threading
import time
from collections.abc import Callable

log = logging.getLogger(__name__)


class Enrollment:
    def __init__(self, get_frame: Callable, recognizer, total: int = 6, interval: float = 2.5,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._get_frame = get_frame
        self._recognizer = recognizer
        self._total = total
        self._interval = interval
        self._sleep = sleep
        self._verrou = threading.Lock()
        self._etat = {"etat": "libre", "fait": 0, "total": total, "ajoutes": 0}
        self._thread: threading.Thread | None = None

    @property
    def en_cours(self) -> bool:
        return self._etat["etat"] == "en_cours"

    def status(self) -> dict:
        return dict(self._etat)

    def start(self, name: str) -> bool:
        """Lance l'enrôlement en arrière-plan. False si un autre est déjà en cours."""
        if not self._verrou.acquire(blocking=False):
            return False
        self._etat = {"etat": "en_cours", "fait": 0, "total": self._total, "ajoutes": 0}
        self._thread = threading.Thread(target=self._run, args=(name,), name="beedoo-enrolement", daemon=True)
        self._thread.start()
        return True

    def join(self, timeout: float = 5.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self, name: str) -> None:
        try:
            for _ in range(self._total):
                self._sleep(self._interval)
                try:
                    frame = self._get_frame()
                    if frame is not None:
                        self._etat["ajoutes"] += self._recognizer.enroll(name, [frame])
                except Exception as erreur:
                    log.warning("image d'enrôlement ignorée (%s)", type(erreur).__name__)
                self._etat["fait"] += 1
            self._etat["etat"] = "termine" if self._etat["ajoutes"] else "echec"
            log.info("enrôlement fini : %d empreintes sur %d images", self._etat["ajoutes"], self._total)
        finally:
            self._verrou.release()
