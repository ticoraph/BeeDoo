"""Suivi du visage : la tête de BeeDoo tourne (de gauche à droite seulement) vers la personne.

Le daemon du robot détecte le visage (SDK : `start_head_tracking`, détecteur YuNet) mais son propre
mouvement ajoute 15° de tangage à chaque détection et fait hocher la tête (voir DECISIONS.md, « Suivi du
visage »). BeeDoo n'utilise donc que la **détection** : le suivi du daemon est allumé avec un poids minuscule
(le détecteur reste actif, la tête ne bouge presque pas sous son effet), BeeDoo lit `get_tracked_face()` et
commande lui-même le lacet avec `set_target()`. Le tangage reste à 0. Aucune image ne passe par ce module.

Pendant un geste qui bouge la tête (OUI, NON, regarder), la boucle n'envoie plus rien (sinon elle
reprendrait la main sur le geste) ; à la fin du geste elle repart du neutre, où tous les gestes se terminent.
Les pauses se cumulent (compteur).
"""

import logging
import math
import threading
import time

from reachy_mini.utils import create_head_pose

log = logging.getLogger(__name__)

POIDS_DAEMON = 0.005  # > 0 : le détecteur du daemon reste actif ; assez bas pour ne pas bouger la tête
FREQUENCE = 30.0  # Hz, boucle de commande (voir reachy-control-loops)

# Un visage au bord de l'image est à ±41° de l'axe de la caméra (Lite, 1920x1080, mesuré avec
# look_at_image_pose) : tan(41°) = 0,86.
TAN_DEMI_CHAMP = 0.86
LACET_MAX = 40.0  # degrés, la tête ne tourne jamais plus loin
ZONE_MORTE = 4.0  # degrés : un visage à moins de 4° du centre ne fait pas bouger la tête
GAIN = 0.6  # part de l'écart corrigée à chaque nouvelle observation (< 1 : pas de dépassement malgré le retard)
CONSTANTE_TEMPS = 0.25  # secondes, lissage du mouvement vers la cible
VITESSE_MAX = 40.0  # degrés par seconde en suivant un visage
VITESSE_RETOUR = 20.0  # degrés par seconde pour revenir au centre
PERTE = 3.0  # secondes sans visage avant de revenir au centre
SEUIL_REPOS = 0.3  # degrés : en dessous, la tête est considérée comme au centre


def erreur_lacet(x: float) -> float:
    """Angle (degrés) dont il faut tourner la tête pour viser un visage à la position x (−1 à 1, + = à droite).

    Positif = tourner à gauche (convention du SDK) : un visage à droite donne donc un angle négatif.
    """
    return -math.degrees(math.atan(x * TAN_DEMI_CHAMP))


class CibleLacet:
    """Calcule le lacet à envoyer à partir des positions du visage. Pur calcul : ni robot, ni horloge, ni fil."""

    def __init__(self) -> None:
        self.lacet = 0.0  # degrés, dernière valeur envoyée
        self._cible = 0.0
        self._derniere_obs: float | None = None  # horodatage de la dernière observation prise en compte
        self._vu_a: float | None = None  # instant de la dernière détection

    def recaler(self, lacet: float) -> None:
        """Repart de cette valeur commandée (après un geste, le neutre)."""
        self.lacet = self._cible = max(-LACET_MAX, min(LACET_MAX, lacet))
        self._vu_a = None

    def oublier(self) -> None:
        """Ne regarde plus personne : la tête revient au centre sans attendre le délai de perte."""
        self._vu_a = None

    def observer(self, x: float | None, horodatage: float | None, maintenant: float) -> None:
        """Position du visage lue au daemon (x de −1 à 1, None = aucun visage).

        Une même observation relue plusieurs fois (même horodatage) ne compte qu'une fois : sinon la
        correction serait appliquée plusieurs fois avant que la caméra ait vu la tête bouger.
        """
        if x is None:
            return
        if horodatage is not None and horodatage == self._derniere_obs:
            return
        self._derniere_obs = horodatage
        self._vu_a = maintenant
        ecart = erreur_lacet(max(-1.0, min(1.0, x)))
        if abs(ecart) <= ZONE_MORTE:
            self._cible = self.lacet
        else:
            ecart -= math.copysign(ZONE_MORTE, ecart)
            self._cible = max(-LACET_MAX, min(LACET_MAX, self.lacet + GAIN * ecart))

    def avancer(self, dt: float, maintenant: float) -> float:
        """Fait avancer la tête de `dt` secondes vers la cible et renvoie le lacet à envoyer."""
        perdu = self._vu_a is None or maintenant - self._vu_a > PERTE
        if perdu:
            self._cible = 0.0
        vitesse = VITESSE_RETOUR if perdu else VITESSE_MAX
        pas = (self._cible - self.lacet) * min(1.0, dt / CONSTANTE_TEMPS)
        pas = max(-vitesse * dt, min(vitesse * dt, pas))
        self.lacet += pas
        return self.lacet

    @property
    def au_repos(self) -> bool:
        return abs(self.lacet) < SEUIL_REPOS and abs(self._cible) < SEUIL_REPOS


class HeadTracker:
    def __init__(self, mini, voulu: bool = True) -> None:
        self._mini = mini
        self._voulu = voulu  # réglage de l'utilisateur
        self._pauses = 0
        self._demarre = False
        self._a_recaler = True
        self._verrou = threading.Lock()
        self._calcul = CibleLacet()
        self._arret = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def actif(self) -> bool:
        """Vrai si le suivi pilote la tête en ce moment."""
        return self._demarre and self._voulu and self._pauses == 0

    def start(self) -> None:
        with self._verrou:
            if self._demarre:
                return
            self._demarre = True
            self._a_recaler = True
            self._appliquer()
        self._arret.clear()
        self._thread = threading.Thread(target=self._boucle, name="suivi-visage", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._verrou:
            self._demarre = False
            self._pauses = 0
            self._envoyer(self._mini.stop_head_tracking)
        self._arret.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def set_voulu(self, voulu: bool) -> None:
        with self._verrou:
            self._voulu = voulu
            self._appliquer()

    def pause(self) -> None:
        # Le verrou est aussi pris par la boucle autour de chaque envoi : une fois `pause()` revenu,
        # plus aucune commande de la boucle ne part, le geste peut commencer.
        with self._verrou:
            self._pauses += 1

    def resume(self) -> None:
        with self._verrou:
            self._pauses = max(0, self._pauses - 1)
            self._a_recaler = True

    def _appliquer(self) -> None:
        """Allume le détecteur du daemon (poids minuscule) ou l'éteint si l'utilisateur ne veut pas du suivi."""
        if not self._demarre:
            return
        if not self._voulu:
            self._envoyer(self._mini.stop_head_tracking)
        else:
            self._envoyer(lambda: self._mini.start_head_tracking(weight=POIDS_DAEMON))

    def _boucle(self) -> None:
        periode = 1.0 / FREQUENCE
        precedent = time.monotonic()
        erreurs = 0
        while not self._arret.wait(periode):
            maintenant = time.monotonic()
            dt, precedent = maintenant - precedent, maintenant
            try:
                self._tour(dt, maintenant)
                erreurs = 0
            except Exception as erreur:  # le daemon peut être parti : le suivi n'est pas vital
                erreurs += 1
                if erreurs in (1, 100):
                    log.warning("suivi du visage : tour impossible (%d de suite, %s)", erreurs, type(erreur).__name__)

    def _tour(self, dt: float, maintenant: float) -> None:
        face = self._lire_visage() if self._voulu else None
        with self._verrou:
            if not self._demarre or self._pauses > 0:
                return
            if self._a_recaler:
                # On repart du neutre commandé : tous les gestes y finissent. La pose lue sur le robot n'est
                # pas fiable à quelques degrés près (jeu mécanique, mesuré : 0° commandé donne −4° à +5°).
                self._calcul.recaler(0.0)
                self._a_recaler = False
            if not self._voulu:
                self._calcul.oublier()
            elif face is not None:
                self._calcul.observer(face.x, face.ts, maintenant)
            lacet = self._calcul.avancer(dt, maintenant)
            if self._voulu or not self._calcul.au_repos:  # coupé et revenu au centre : on lâche la tête
                self._mini.set_target(head=create_head_pose(yaw=lacet, degrees=True))

    def _lire_visage(self):
        cible = self._mini.get_tracked_face(wait=False)
        return cible if cible is not None and cible.detected and cible.x is not None else None

    @staticmethod
    def _envoyer(commande) -> None:
        try:
            commande()
        except Exception as erreur:  # le daemon peut être parti : le suivi n'est pas vital
            log.warning("suivi du visage : commande impossible (%s)", type(erreur).__name__)
