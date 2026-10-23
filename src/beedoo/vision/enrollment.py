"""Enrôlement d'une personne par la caméra : quelques images valides, à quelques secondes d'intervalle.

On ne garde que les empreintes (jamais les images). La personne est invitée à tourner doucement la
tête entre deux prises, pour que l'empreinte couvre plusieurs poses (voir l'essai S3). Seules les images
où un visage assez grand est trouvé comptent : on laisse jusqu'à deux fois plus d'essais que d'images
voulues, et on dit à la personne ce qui manque (trop loin, personne en vue).
"""

import logging
import threading
import time
from collections.abc import Callable

from beedoo.vision.faces import MIN_FACE_PIXELS

log = logging.getLogger(__name__)


class Enrollment:
    def __init__(self, get_frame: Callable, recognizer, total: int = 6, interval: float = 2.5,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._get_frame = get_frame
        self._recognizer = recognizer
        self._total = total
        self._max_essais = total * 2
        self._interval = interval
        self._sleep = sleep
        self._verrou = threading.Lock()
        self._etat = self._neuf("libre")
        self._thread: threading.Thread | None = None

    def _neuf(self, etat: str) -> dict:
        return {"etat": etat, "ajoutes": 0, "total": self._total, "essais": 0,
                "derniere": None, "taille": None, "min_taille": MIN_FACE_PIXELS}

    @property
    def en_cours(self) -> bool:
        return self._etat["etat"] == "en_cours"

    def status(self) -> dict:
        return dict(self._etat)

    def start(self, name: str) -> bool:
        """Lance l'enrôlement en arrière-plan. False si un autre est déjà en cours."""
        if not self._verrou.acquire(blocking=False):
            return False
        self._etat = self._neuf("en_cours")
        self._thread = threading.Thread(target=self._run, args=(name,), name="beedoo-enrolement", daemon=True)
        self._thread.start()
        return True

    def join(self, timeout: float = 5.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self, name: str) -> None:
        try:
            while self._etat["ajoutes"] < self._total and self._etat["essais"] < self._max_essais:
                self._sleep(self._interval)
                statut, taille = "aucune_image", None
                try:
                    frame = self._get_frame()
                    if frame is not None:
                        lecture = self._recognizer.enroll_image(name, frame)
                        statut, taille = lecture.statut, lecture.taille
                except Exception as erreur:
                    statut = "erreur"
                    log.warning("image d'enrôlement ignorée (%s)", type(erreur).__name__)
                self._etat["essais"] += 1
                self._etat["derniere"], self._etat["taille"] = statut, taille
                if statut == "ok":
                    self._etat["ajoutes"] += 1
            self._etat["etat"] = "termine" if self._etat["ajoutes"] >= 3 else "echec"
            log.info("enrôlement fini : %d empreintes en %d essais", self._etat["ajoutes"], self._etat["essais"])
        finally:
            self._verrou.release()
