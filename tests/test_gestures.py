import threading
import time

import pytest

pytest.importorskip("reachy_mini")

from beedoo.gestures.library import DUREE_MIN, GESTES, Step, regarder
from beedoo.gestures.player import GesturePlayer


class FauxRobot:
    def __init__(self, delai: float = 0.0) -> None:
        self.appels: list[dict] = []
        self.delai = delai

    def goto_target(self, **kwargs) -> None:
        self.appels.append(kwargs)
        time.sleep(self.delai)


def attendre(player: GesturePlayer) -> None:
    deadline = time.time() + 5
    while player.occupe and time.time() < deadline:
        time.sleep(0.01)
    assert not player.occupe


def test_every_gesture_is_slow_and_bounded():
    for nom, geste in GESTES.items():
        etapes = geste()
        assert etapes, nom
        assert all(e.duree >= DUREE_MIN for e in etapes), nom


def test_step_refuses_too_fast_or_too_wide():
    with pytest.raises(ValueError):
        Step(duree=0.2, tangage=5)
    with pytest.raises(ValueError):
        Step(lacet=90)
    with pytest.raises(ValueError):
        Step(antennes=(100, 0))


def test_regarder_clamps_angles():
    etape = regarder(lacet=200, tangage=-200)[0]
    assert etape.lacet == 45 and etape.tangage == -25


def test_gesture_ends_with_neutral():
    robot = FauxRobot()
    player = GesturePlayer(robot)
    assert player.play("oui")
    attendre(player)
    assert len(robot.appels) == len(GESTES["oui"]()) + 1
    dernier = robot.appels[-1]
    assert dernier["antennas"] == [0.0, 0.0] and dernier["head"] is not None
    assert all(a["duration"] >= DUREE_MIN for a in robot.appels)


def test_antenna_only_step_keeps_head():
    robot = FauxRobot()
    player = GesturePlayer(robot)
    player.play("antennes_content")
    attendre(player)
    assert robot.appels[0]["head"] is None


def test_second_gesture_refused_while_busy():
    robot = FauxRobot(delai=0.2)
    player = GesturePlayer(robot)
    assert player.play("non")
    assert not player.play("oui")
    player.stop()
    attendre(player)


def test_unknown_gesture_and_bad_params():
    player = GesturePlayer(FauxRobot())
    with pytest.raises(KeyError):
        player.play("danse")
    with pytest.raises(ValueError):
        player.play("oui", force=3)


def test_stop_aborts_remaining_steps_without_neutral():
    robot = FauxRobot(delai=0.1)
    player = GesturePlayer(robot)
    player.play("antennes_content")
    time.sleep(0.15)
    player.stop()
    assert len(robot.appels) < len(GESTES["antennes_content"]())


def test_robot_error_releases_player():
    class Casse(FauxRobot):
        def goto_target(self, **kwargs):
            raise ConnectionError("daemon parti")

    player = GesturePlayer(Casse())
    player.play("oui")
    attendre(player)


class FauxSuivi:
    def __init__(self):
        self.evenements = []

    def pause(self):
        self.evenements.append("pause")

    def resume(self):
        self.evenements.append("reprise")


def test_head_gesture_pauses_tracking_then_resumes():
    robot, suivi = FauxRobot(), FauxSuivi()
    player = GesturePlayer(robot, suivi)
    player.play("oui")
    attendre(player)
    assert suivi.evenements == ["pause", "reprise"]


def test_antenna_gesture_leaves_head_to_tracking():
    robot, suivi = FauxRobot(), FauxSuivi()
    player = GesturePlayer(robot, suivi)
    player.play("antennes_content")
    attendre(player)
    assert suivi.evenements == []  # le suivi n'est pas interrompu
    assert all(a["head"] is None for a in robot.appels)  # pas même au retour au repos
    assert all(a.get("body_yaw", 0) is None for a in robot.appels)  # le corps garde son orientation
    assert robot.appels[-1]["antennas"] == [0.0, 0.0]


def test_tracking_resumes_even_if_the_robot_fails():
    class Casse(FauxRobot):
        def goto_target(self, **kwargs):
            raise ConnectionError("daemon parti")

    suivi = FauxSuivi()
    player = GesturePlayer(Casse(), suivi)
    player.play("non")
    attendre(player)
    assert suivi.evenements == ["pause", "reprise"]
