import threading

from beedoo.vision.enrollment import Enrollment
from beedoo.vision.faces import Lecture


class FauxReconnaisseur:
    def __init__(self, lectures):
        self.lectures = list(lectures)
        self.noms = []

    def enroll_image(self, nom, image):
        self.noms.append(nom)
        return self.lectures.pop(0)


OK = Lecture("ok", 120)
LOIN = Lecture("trop_petit", 50)
PERSONNE = Lecture("aucun_visage")


def lancer(lectures, total=3, frames=None):
    reco = FauxReconnaisseur(lectures)
    suite = iter(frames if frames is not None else [object()] * len(lectures))
    enrolement = Enrollment(get_frame=lambda: next(suite), recognizer=reco, total=total, interval=0,
                            sleep=lambda s: None)
    assert enrolement.start("Léa")
    enrolement.join()
    return enrolement, reco


def test_success_stops_once_enough_valid_images():
    enrolement, reco = lancer([OK, OK, OK, OK], total=3)
    statut = enrolement.status()
    assert statut["etat"] == "termine" and statut["ajoutes"] == 3 and statut["essais"] == 3
    assert reco.noms == ["Léa"] * 3
    assert not enrolement.en_cours


def test_invalid_images_do_not_count_but_allow_more_tries():
    enrolement, _ = lancer([LOIN, PERSONNE, OK, OK, LOIN, OK], total=3)
    statut = enrolement.status()
    assert statut["etat"] == "termine" and statut["ajoutes"] == 3 and statut["essais"] == 6


def test_failure_tells_why():
    enrolement, _ = lancer([LOIN] * 6, total=3)
    statut = enrolement.status()
    assert statut["etat"] == "echec" and statut["ajoutes"] == 0
    assert statut["derniere"] == "trop_petit" and statut["taille"] == 50
    assert statut["min_taille"] > 50


def test_two_valid_images_are_not_enough():
    enrolement, _ = lancer([OK, OK] + [PERSONNE] * 4, total=3)
    assert enrolement.status()["etat"] == "echec"


def test_missing_frames_are_skipped():
    enrolement, reco = lancer([OK], total=1, frames=[None, object()])
    assert enrolement.status()["ajoutes"] == 1 and len(reco.noms) == 1


def test_camera_error_does_not_crash():
    def casse():
        raise ConnectionError("caméra")

    enrolement = Enrollment(get_frame=casse, recognizer=FauxReconnaisseur([]), total=2, interval=0,
                            sleep=lambda s: None)
    enrolement.start("Léa")
    enrolement.join()
    statut = enrolement.status()
    assert statut["etat"] == "echec" and statut["derniere"] == "erreur" and statut["essais"] == 4


def test_second_start_refused_while_running():
    porte = threading.Event()
    enrolement = Enrollment(get_frame=lambda: None, recognizer=FauxReconnaisseur([]), total=1, interval=0,
                            sleep=lambda s: porte.wait(2))
    assert enrolement.start("Léa")
    assert not enrolement.start("Paul")
    porte.set()
    enrolement.join()


def test_after_callback_runs_only_on_success():
    appeles = []
    enrolement, _ = lancer([OK, OK, OK], total=3)
    enrolement.start("Léa", apres=appeles.append)
    enrolement.join()
    assert appeles == []  # plus d'images : l'enrôlement a échoué
    reco = FauxReconnaisseur([OK, OK, OK])
    suite = iter([object()] * 3)
    reussi = Enrollment(get_frame=lambda: next(suite), recognizer=reco, total=3, interval=0, sleep=lambda s: None)
    reussi.start("Léa", apres=appeles.append)
    reussi.join()
    assert appeles == ["Léa"] and reussi.status()["etat"] == "termine"


def test_failing_after_callback_does_not_fail_the_enrollment():
    def casse(nom):
        raise OSError("disque plein")

    reco = FauxReconnaisseur([OK, OK, OK])
    suite = iter([object()] * 3)
    enrolement = Enrollment(get_frame=lambda: next(suite), recognizer=reco, total=3, interval=0,
                            sleep=lambda s: None)
    enrolement.start("Léa", apres=casse)
    enrolement.join()
    assert enrolement.status()["etat"] == "termine"
