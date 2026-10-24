import math
import time
from types import SimpleNamespace

import numpy as np
import pytest

from beedoo import tracking
from beedoo.tracking import LACET_MAX, PERTE, POIDS_DAEMON, ZONE_MORTE, CibleLacet, HeadTracker, erreur_lacet
from reachy_mini.utils import create_head_pose


def lacet_de(pose) -> float:
    return math.degrees(math.atan2(pose[1][0], pose[0][0]))


def tangage_de(pose) -> float:
    return math.degrees(math.asin(-pose[2][0]))


class FauxRobot:
    def __init__(self):
        self.commandes = []
        self.visage = SimpleNamespace(detected=False, x=None, y=None, ts=0.0)
        self.pose = create_head_pose()

    def start_head_tracking(self, weight=1.0):
        self.commandes.append(("suivi", weight))

    def stop_head_tracking(self):
        self.commandes.append(("arret",))

    def get_tracked_face(self, wait=True, timeout=5.0):
        return self.visage

    def get_current_head_pose(self):
        return self.pose

    def set_target(self, head=None, antennas=None, body_yaw=None):
        self.commandes.append(("tete", head))

    def voir(self, x, ts):
        self.visage = SimpleNamespace(detected=True, x=x, y=0.0, ts=ts)

    def envois(self):
        return [c[1] for c in self.commandes if c[0] == "tete"]


@pytest.fixture
def sans_boucle(monkeypatch):
    """Les tests appellent `_tour()` eux-mêmes : pas de fil de fond, rien d'aléatoire."""
    monkeypatch.setattr(HeadTracker, "_boucle", lambda self: None)


# --- calcul pur -----------------------------------------------------------------------------------------------

def test_face_on_the_right_means_turning_right():
    assert erreur_lacet(0.0) == 0.0
    assert erreur_lacet(1.0) == pytest.approx(-40.7, abs=0.5)  # bord de l'image = ±41° (mesuré)
    assert erreur_lacet(-1.0) == pytest.approx(40.7, abs=0.5)


def test_small_offset_is_ignored():
    calcul = CibleLacet()
    calcul.observer(0.05, 1.0, 0.0)  # ~2,5° : dans la zone morte
    for i in range(30):
        assert calcul.avancer(1 / 30, i / 30) == 0.0


def test_head_turns_toward_the_face():
    calcul = CibleLacet()
    calcul.observer(0.6, 1.0, 0.0)  # visage à droite
    for i in range(10):
        calcul.avancer(1 / 30, i / 30)
    assert calcul.lacet < -1.0
    calcul = CibleLacet()
    calcul.observer(-0.6, 1.0, 0.0)  # visage à gauche
    for i in range(10):
        calcul.avancer(1 / 30, i / 30)
    assert calcul.lacet > 1.0


def test_same_observation_counts_once():
    calcul = CibleLacet()
    calcul.observer(0.6, 5.0, 0.0)
    premiere_cible = calcul._cible
    for i in range(6):  # la tête avance, la caméra n'a encore rien de nouveau
        calcul.avancer(1 / 30, i / 30)
        calcul.observer(0.6, 5.0, i / 30)  # même horodatage : valeur périmée relue
    assert calcul._cible == premiere_cible
    calcul.observer(0.6, 5.1, 0.2)  # nouvelle observation : elle compte
    assert calcul._cible != premiere_cible


def test_never_goes_past_the_limit_or_the_max_speed():
    calcul = CibleLacet()
    precedent = 0.0
    for i in range(300):
        calcul.observer(1.0, float(i), i / 30)  # visage collé au bord, sans fin
        lacet = calcul.avancer(1 / 30, i / 30)
        assert abs(lacet) <= LACET_MAX + 1e-9
        assert abs(lacet - precedent) <= tracking.VITESSE_MAX / 30 + 1e-9
        precedent = lacet


def test_closed_loop_converges_without_oscillating():
    """Une personne immobile à 25° sur la gauche ; la caméra voit avec 0,2 s de retard, 10 observations par seconde."""
    azimut = 25.0
    calcul = CibleLacet()
    historique = [0.0] * 8  # lacets passés (retard de la caméra)
    lacets = []
    dt = 1 / 30
    for i in range(30 * 8):
        t = i * dt
        if i % 3 == 0:
            vu = historique[-7]  # la caméra voit la tête telle qu'elle était 0,2 s plus tôt
            x = -math.tan(math.radians(azimut - vu)) / tracking.TAN_DEMI_CHAMP  # à gauche = x négatif
            calcul.observer(x, t, t)
        lacet = calcul.avancer(dt, t)
        historique.append(lacet)
        lacets.append(lacet)
    assert max(lacets) < azimut + ZONE_MORTE  # pas de dépassement notable
    assert abs(lacets[-1] - azimut) <= ZONE_MORTE + 1.0  # arrivé (à la zone morte près)
    derniere_seconde = lacets[-30:]
    assert max(derniere_seconde) - min(derniere_seconde) < 1.0  # et stable, sans va-et-vient


def test_holds_then_returns_to_center_after_losing_the_face():
    calcul = CibleLacet()
    t = 0.0
    for i in range(60):  # on s'oriente vers un visage à gauche
        t = i / 30
        calcul.observer(-0.8, float(i), t)
        calcul.avancer(1 / 30, t)
    garde = calcul.lacet
    assert garde > 10
    t += PERTE - 0.5  # visage perdu depuis moins de PERTE : la tête reste
    assert calcul.avancer(1 / 30, t) == pytest.approx(garde, abs=0.5)
    for i in range(30 * 6):  # perdu depuis longtemps : retour au centre, doucement
        t += 1 / 30
        calcul.avancer(1 / 30, t)
    assert abs(calcul.lacet) < 0.3 and calcul.au_repos


def test_recaler_starts_from_the_real_head_position():
    calcul = CibleLacet()
    calcul.recaler(12.0)
    assert calcul.lacet == 12.0
    calcul.recaler(200.0)
    assert calcul.lacet == LACET_MAX


# --- lien avec le daemon -----------------------------------------------------------------------------------------

def test_nothing_is_sent_before_start():
    robot = FauxRobot()
    suivi = HeadTracker(robot)
    suivi.pause()
    suivi.set_voulu(False)
    assert robot.commandes == [] and not suivi.actif


def test_start_pause_resume_stop():
    robot = FauxRobot()
    suivi = HeadTracker(robot)
    suivi.start()
    assert suivi.actif
    suivi.pause()
    assert not suivi.actif
    suivi.resume()
    assert suivi.actif
    suivi.stop()
    assert ("suivi", POIDS_DAEMON) in robot.commandes and robot.commandes[-1] == ("arret",)
    assert POIDS_DAEMON < 0.05  # le daemon ne doit pas bouger la tête lui-même


def test_pauses_add_up():
    robot = FauxRobot()
    suivi = HeadTracker(robot)
    suivi.start()
    suivi.pause()
    suivi.pause()
    suivi.resume()
    assert not suivi.actif  # une pause reste
    suivi.resume()
    assert suivi.actif
    suivi.resume()  # reprise en trop : ne passe pas sous zéro
    suivi.pause()
    assert not suivi.actif
    suivi.stop()


def test_user_switch_stops_tracking_even_when_not_paused():
    robot = FauxRobot()
    suivi = HeadTracker(robot, voulu=True)
    suivi.start()
    suivi.set_voulu(False)
    assert robot.commandes[-1] == ("arret",) and not suivi.actif
    suivi.pause()
    suivi.resume()
    assert robot.commandes[-1] == ("arret",)  # les pauses ne rallument pas un suivi coupé
    suivi.set_voulu(True)
    assert robot.commandes[-1] == ("suivi", POIDS_DAEMON)
    suivi.stop()


def test_unwanted_at_start_stays_off():
    robot = FauxRobot()
    suivi = HeadTracker(robot, voulu=False)
    suivi.start()
    assert robot.commandes == [("arret",)] and not suivi.actif
    suivi.stop()


def test_daemon_error_is_not_fatal():
    class Casse(FauxRobot):
        def start_head_tracking(self, weight=1.0):
            raise ConnectionError("daemon parti")

        def get_tracked_face(self, wait=True, timeout=5.0):
            raise ConnectionError("daemon parti")

    suivi = HeadTracker(Casse())
    suivi.start()
    suivi.pause()
    suivi.resume()
    time.sleep(0.1)  # la boucle essaie, échoue, continue
    suivi.stop()


def test_head_command_turns_only_the_yaw(sans_boucle):
    robot = FauxRobot()
    suivi = HeadTracker(robot)
    suivi.start()
    robot.voir(0.7, 1.0)  # visage à droite
    for i in range(20):
        suivi._tour(1 / 30, i / 30)
    pose = robot.envois()[-1]
    assert lacet_de(pose) < -2.0  # tourne à droite
    assert tangage_de(pose) == pytest.approx(0.0, abs=1e-6)  # jamais de hochement
    assert all(tangage_de(p) == pytest.approx(0.0, abs=1e-6) for p in robot.envois())
    suivi.stop()


def test_nothing_is_sent_during_a_gesture_then_resumes_from_neutral(sans_boucle):
    robot = FauxRobot()
    robot.voir(-0.9, 1.0)  # visage à gauche : la tête tourne
    suivi = HeadTracker(robot)
    suivi.start()
    for i in range(30):
        suivi._tour(1 / 30, i / 30)
    assert lacet_de(robot.envois()[-1]) > 5.0
    avant = len(robot.envois())
    suivi.pause()  # un geste commence (il finit au neutre)
    for i in range(30, 40):
        suivi._tour(1 / 30, i / 30)
    assert len(robot.envois()) == avant  # la boucle se tait
    robot.visage = SimpleNamespace(detected=False, x=None, y=None, ts=0.0)
    suivi.resume()
    suivi._tour(1 / 30, 2.0)
    assert lacet_de(robot.envois()[-1]) == pytest.approx(0.0, abs=0.01)  # repart du neutre, sans saut
    suivi.stop()


def test_switching_off_returns_to_center_then_releases_the_head(sans_boucle):
    robot = FauxRobot()
    suivi = HeadTracker(robot)
    suivi.start()
    robot.voir(-0.9, 1.0)
    for i in range(60):
        suivi._tour(1 / 30, i / 30)
    assert lacet_de(robot.envois()[-1]) > 10
    suivi.set_voulu(False)
    for i in range(60, 60 + 30 * 3):
        suivi._tour(1 / 30, i / 30)
    assert lacet_de(robot.envois()[-1]) == pytest.approx(0.0, abs=0.5)  # revenue au centre malgré le visage
    avant = len(robot.envois())
    for i in range(30):
        suivi._tour(1 / 30, 10.0 + i / 30)
    assert len(robot.envois()) == avant  # puis plus aucune commande : la tête est libre
    suivi.stop()


def test_real_loop_runs_and_stops_cleanly():
    robot = FauxRobot()
    robot.voir(0.8, 1.0)
    suivi = HeadTracker(robot)
    suivi.start()
    time.sleep(0.3)
    suivi.stop()
    assert robot.envois()  # la boucle a commandé la tête
    assert suivi._thread is None
    nombre = len(robot.envois())
    time.sleep(0.15)
    assert len(robot.envois()) == nombre  # et elle s'est bien arrêtée
