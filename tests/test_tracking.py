from beedoo.tracking import HeadTracker


class FauxRobot:
    def __init__(self):
        self.commandes = []

    def start_head_tracking(self, weight=1.0):
        self.commandes.append(("suivi", weight))

    def stop_head_tracking(self):
        self.commandes.append(("arret",))


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
    assert robot.commandes == [("suivi", 1.0), ("suivi", 0.0), ("suivi", 1.0), ("arret",)]


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
    assert robot.commandes[-1] == ("suivi", 1.0)


def test_unwanted_at_start_stays_off():
    robot = FauxRobot()
    suivi = HeadTracker(robot, voulu=False)
    suivi.start()
    assert robot.commandes == [("arret",)] and not suivi.actif


def test_daemon_error_is_not_fatal():
    class Casse(FauxRobot):
        def start_head_tracking(self, weight=1.0):
            raise ConnectionError("daemon parti")

    suivi = HeadTracker(Casse())
    suivi.start()
    suivi.pause()
    suivi.resume()
