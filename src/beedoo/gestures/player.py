"""Lecteur de gestes : un seul geste à la fois, toujours terminé par un retour au neutre.

`goto_target()` bloque pendant le mouvement : le geste tourne donc dans un thread, et l'appelant
(interface web, plus tard conversation) n'attend pas. Voir `reachy-motion-philosophy`.
"""

import logging
import math
import threading

from reachy_mini.utils import create_head_pose

from beedoo.gestures.library import GESTES, Step, neutre

log = logging.getLogger(__name__)

ANTENNES_REPOS = (0.0, 0.0)


class GesturePlayer:
    def __init__(self, mini) -> None:
        self._mini = mini
        self._occupe = threading.Lock()
        self._abandon = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def occupe(self) -> bool:
        return self._occupe.locked()

    def play(self, nom: str, **parametres) -> bool:
        """Lance le geste en arrière-plan. False si un geste est déjà en cours.

        Lève KeyError pour un geste inconnu, ValueError pour des paramètres refusés.
        """
        if nom not in GESTES:
            raise KeyError(nom)
        try:
            etapes = GESTES[nom](**parametres)
        except TypeError as erreur:
            raise ValueError(f"paramètres invalides pour {nom}") from erreur
        if not self._occupe.acquire(blocking=False):
            return False
        self._abandon.clear()
        self._thread = threading.Thread(target=self._jouer, args=(nom, etapes), name=f"geste-{nom}", daemon=True)
        self._thread.start()
        return True

    def stop(self, attente: float = 5.0) -> None:
        """Interrompt le geste en cours (après son étape actuelle) et attend sa fin."""
        self._abandon.set()
        if self._thread is not None:
            self._thread.join(timeout=attente)

    def _jouer(self, nom: str, etapes: tuple[Step, ...]) -> None:
        log.info("geste : %s", nom)
        try:
            for etape in etapes:
                if self._abandon.is_set():
                    break
                self._executer(etape)
            if nom != "neutre" and not self._abandon.is_set():
                for etape in neutre():
                    self._executer(etape)
        except Exception:
            # Une erreur de connexion ne doit pas faire tomber l'application.
            log.exception("geste %s interrompu par une erreur", nom)
        finally:
            self._occupe.release()

    def _executer(self, etape: Step) -> None:
        # Quand la tête bouge, un angle non précisé vaut 0 ; sinon la tête reste où elle est.
        tete = None
        if etape.bouge_la_tete:
            tete = create_head_pose(
                pitch=etape.tangage or 0.0, yaw=etape.lacet or 0.0, roll=etape.roulis or 0.0, degrees=True
            )
        antennes = None if etape.antennes is None else [math.radians(a) for a in etape.antennes]
        self._mini.goto_target(head=tete, antennas=antennes, duration=etape.duree, method="minjerk")
        if etape.pause:
            self._abandon.wait(etape.pause)
