"""Suivi du visage : la tête de BeeDoo tourne vers la personne la plus proche.

La détection et le mouvement se font dans le daemon du robot (SDK : `start_head_tracking`, détecteur
YuNet) : BeeDoo n'a qu'à l'allumer, l'éteindre ou le mettre en pause. Aucune image ne passe par ce module.

Pendant un geste qui bouge la tête (OUI, NON, regarder), le suivi est mis en pause (poids 0) sinon il
reprendrait la main sur la tête ; il reprend à la fin du geste. Les pauses se cumulent (compteur).
"""

import logging
import threading

log = logging.getLogger(__name__)


class HeadTracker:
    def __init__(self, mini, voulu: bool = True) -> None:
        self._mini = mini
        self._voulu = voulu  # réglage de l'utilisateur
        self._pauses = 0
        self._demarre = False
        self._verrou = threading.Lock()

    @property
    def actif(self) -> bool:
        """Vrai si le suivi pilote la tête en ce moment."""
        return self._demarre and self._voulu and self._pauses == 0

    def start(self) -> None:
        with self._verrou:
            self._demarre = True
            self._appliquer()

    def stop(self) -> None:
        with self._verrou:
            self._demarre = False
            self._pauses = 0
            self._envoyer(self._mini.stop_head_tracking)

    def set_voulu(self, voulu: bool) -> None:
        with self._verrou:
            self._voulu = voulu
            self._appliquer()

    def pause(self) -> None:
        with self._verrou:
            self._pauses += 1
            self._appliquer()

    def resume(self) -> None:
        with self._verrou:
            self._pauses = max(0, self._pauses - 1)
            self._appliquer()

    def _appliquer(self) -> None:
        if not self._demarre:
            return
        if not self._voulu:
            self._envoyer(self._mini.stop_head_tracking)
        else:
            poids = 1.0 if self._pauses == 0 else 0.0
            self._envoyer(lambda: self._mini.start_head_tracking(weight=poids))

    @staticmethod
    def _envoyer(commande) -> None:
        try:
            commande()
        except Exception as erreur:  # le daemon peut être parti : le suivi n'est pas vital
            log.warning("suivi du visage : commande impossible (%s)", type(erreur).__name__)
