import time

from beedoo.vision.faces import Match
from beedoo.vision.greeter import SALUE, Event, Greeter
from beedoo.vision.loop import VisionLoop


def boucle(matchs, **kwargs):
    """Boucle alimentée par une liste de résultats d'analyse ; les événements sont notés dans `vus`."""
    vus = []
    suite = iter(matchs)
    loop = VisionLoop(get_frame=lambda: object(), identify=lambda frame: next(suite),
                      greeter=Greeter(confirmations=2), on_event=vus.append, **kwargs)
    return loop, vus


def lea():
    return Match("lea", 0.1, 0.5)


def test_step_greets_after_two_identical_frames():
    loop, _ = boucle([lea(), lea()])
    assert loop.step() is None
    assert loop.step() == Event(SALUE, "lea")


def test_no_frame_does_nothing():
    loop = VisionLoop(get_frame=lambda: None, identify=lambda f: 1 / 0, greeter=Greeter(), on_event=print)
    assert loop.step() is None  # l'analyse n'est même pas tentée


def test_ambiguous_frame_is_ignored():
    loop, _ = boucle([lea(), Match(None, 0.3, 0.01, "ambigu"), lea()])
    loop.step()
    loop.step()
    assert loop.step() == Event(SALUE, "lea")


def test_no_face_resets_confirmation():
    loop, _ = boucle([lea(), Match(None, None, None, "aucun_visage"), lea()])
    assert [loop.step() for _ in range(3)] == [None, None, None]


def test_thread_delivers_events_and_survives_errors():
    appels = {"n": 0}

    def identify(frame):
        appels["n"] += 1
        if appels["n"] == 1:
            raise RuntimeError("modèle indisponible")
        return lea()

    vus = []
    loop = VisionLoop(get_frame=lambda: object(), identify=identify, greeter=Greeter(confirmations=1),
                      on_event=vus.append, period=0.01)
    loop.start()
    time.sleep(0.2)  # la 1re erreur ralentit (x5), puis la boucle réessaie
    loop.stop()
    assert vus == [Event(SALUE, "lea")]


def test_paused_loop_does_not_analyse():
    loop, vus = boucle([lea()] * 5, period=0.01, active=lambda: False)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    assert vus == []


def test_status_tells_what_is_seen():
    loop, _ = boucle([Match(None, None, None, "trop_petit", 50), Match(None, None, None, "aucun_visage"),
                      Match(None, 0.9, None, "trop_loin", 120), Match("lea", 0.1, 0.5, "", 140)])
    loop.step()
    assert loop.status()["statut"] == "trop_petit" and loop.status()["taille"] == 50
    loop.step()
    assert loop.status()["statut"] == "aucun_visage"
    loop.step()
    assert loop.status()["statut"] == "inconnu"
    loop.step()
    état = loop.status()
    assert état["statut"] == "reconnu" and état["personne"] == "lea" and état["age"] < 1


def test_too_small_face_never_triggers_events_nor_resets():
    loop, _ = boucle([lea(), Match(None, None, None, "trop_petit", 40), lea()])
    loop.step()
    loop.step()
    assert loop.step() == Event(SALUE, "lea")


def test_status_says_pause_and_error():
    loop, _ = boucle([], period=0.01, active=lambda: False)
    loop.start()
    time.sleep(0.1)
    loop.stop()
    assert loop.status()["statut"] == "pause"

    def casse(frame):
        raise RuntimeError("x")

    en_erreur = VisionLoop(get_frame=lambda: object(), identify=casse, greeter=Greeter(), on_event=print,
                           period=0.01)
    en_erreur.start()
    time.sleep(0.1)
    en_erreur.stop()
    assert en_erreur.status()["statut"] == "erreur"
