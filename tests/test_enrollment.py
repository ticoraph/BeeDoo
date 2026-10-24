import threading

from beedoo.vision.enrollment import CLIC, FIN_BONNE, FIN_RATEE, INTRO, POSES, PROBLEMES, Enrollment, Pose
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

TROIS = (Pose("A", "Dis A."), Pose("B", "Dis B."), Pose("C", "Dis C."))


def lancer(lectures, poses=TROIS, frames=None, parle=True):
    reco = FauxReconnaisseur(lectures)
    suite = iter(frames if frames is not None else [object()] * len(lectures))
    dits = []
    pauses = []

    def annoncer(texte):
        dits.append(texte)
        return parle

    enrolement = Enrollment(get_frame=lambda: next(suite), recognizer=reco, annoncer=annoncer, poses=poses,
                            delai=1, interval=5, sleep=pauses.append)
    assert enrolement.start("Léa")
    enrolement.join()
    return enrolement, reco, dits, pauses


def test_success_one_image_per_pose_announced_aloud():
    enrolement, reco, dits, _ = lancer([OK, OK, OK])
    statut = enrolement.status()
    assert statut["etat"] == "termine" and statut["ajoutes"] == 3 and statut["essais"] == 3
    assert reco.noms == ["Léa"] * 3
    assert dits == [INTRO, "Dis A.", CLIC + "Dis B.", CLIC + "Dis C.", CLIC + FIN_BONNE]
    assert not enrolement.en_cours


def test_status_tells_the_current_pose_then_clears_it():
    vus = []
    reco = FauxReconnaisseur([OK, OK, OK])
    enrolement = None

    def annoncer(texte):
        vus.append((enrolement.status()["pose"], enrolement.status()["consigne"]))
        return True

    enrolement = Enrollment(get_frame=lambda: object(), recognizer=reco, annoncer=annoncer, poses=TROIS,
                            delai=0, sleep=lambda s: None)
    enrolement.start("Léa")
    enrolement.join()
    assert (0, "A") in vus and (1, "B") in vus and (2, "C") in vus
    assert enrolement.status()["pose"] is None and enrolement.status()["consigne"] is None


def test_failed_pose_gets_a_second_try_with_the_reason_spoken():
    enrolement, _, dits, _ = lancer([PERSONNE, OK, OK, OK])
    assert enrolement.status()["ajoutes"] == 3 and enrolement.status()["essais"] == 4
    assert dits[1:3] == ["Dis A.", PROBLEMES["aucun_visage"] + " Dis A."]


def test_pose_given_up_after_two_failures_and_next_pose_goes_on_without_click():
    enrolement, _, dits, _ = lancer([LOIN, LOIN, OK, OK])
    assert enrolement.status()["ajoutes"] == 2 and enrolement.status()["etat"] == "echec"
    assert dits[3] == "Dis B."  # pas de « Clic ! » ni de reproche de la pose abandonnée
    assert dits[-1] == FIN_RATEE


def test_failure_tells_why():
    enrolement, _, _, _ = lancer([LOIN] * 6)
    statut = enrolement.status()
    assert statut["etat"] == "echec" and statut["ajoutes"] == 0
    assert statut["derniere"] == "trop_petit" and statut["taille"] == 50
    assert statut["min_taille"] > 50


def test_two_valid_images_are_not_enough():
    enrolement, _, _, _ = lancer([OK, OK, PERSONNE, PERSONNE])
    assert enrolement.status()["etat"] == "echec"


def test_waits_longer_when_the_robot_could_not_speak():
    _, _, _, pauses = lancer([OK, OK, OK], parle=False)
    assert pauses == [1] + [5, 5, 5]  # après l'intro, puis le temps de lire la page pour chaque pose


def test_works_without_any_voice():
    reco = FauxReconnaisseur([OK, OK, OK])
    enrolement = Enrollment(get_frame=lambda: object(), recognizer=reco, poses=TROIS, sleep=lambda s: None)
    enrolement.start("Léa")
    enrolement.join()
    assert enrolement.status()["etat"] == "termine"


def test_speech_error_does_not_stop_the_enrollment():
    def casse(texte):
        raise OSError("haut-parleur")

    reco = FauxReconnaisseur([OK, OK, OK])
    enrolement = Enrollment(get_frame=lambda: object(), recognizer=reco, annoncer=casse, poses=TROIS,
                            sleep=lambda s: None)
    enrolement.start("Léa")
    enrolement.join()
    assert enrolement.status()["etat"] == "termine"


def test_missing_frames_are_skipped():
    enrolement, reco, _, _ = lancer([OK], poses=TROIS[:1], frames=[None, object()])
    assert enrolement.status()["ajoutes"] == 1 and len(reco.noms) == 1


def test_camera_error_does_not_crash():
    def casse():
        raise ConnectionError("caméra")

    enrolement = Enrollment(get_frame=casse, recognizer=FauxReconnaisseur([]), poses=TROIS[:2], sleep=lambda s: None)
    enrolement.start("Léa")
    enrolement.join()
    statut = enrolement.status()
    assert statut["etat"] == "echec" and statut["derniere"] == "erreur" and statut["essais"] == 4


def test_second_start_refused_while_running():
    porte = threading.Event()
    enrolement = Enrollment(get_frame=lambda: None, recognizer=FauxReconnaisseur([]), poses=TROIS[:1],
                            sleep=lambda s: porte.wait(2))
    assert enrolement.start("Léa")
    assert not enrolement.start("Paul")
    porte.set()
    enrolement.join()


def test_cancel_stops_before_the_next_photo_and_skips_the_final_step():
    appeles = []
    reco = FauxReconnaisseur([OK, OK, OK])
    dits = []
    enrolement = None

    def annoncer(texte):
        dits.append(texte)
        if texte.endswith("Dis B."):
            assert enrolement.annuler()
        return True

    enrolement = Enrollment(get_frame=lambda: object(), recognizer=reco, annoncer=annoncer, poses=TROIS,
                            sleep=lambda s: None)
    enrolement.start("Léa", apres=appeles.append)
    enrolement.join()
    assert enrolement.status()["etat"] == "annule" and enrolement.status()["ajoutes"] == 1
    assert appeles == [] and FIN_BONNE not in " ".join(dits)
    assert not enrolement.annuler()  # plus rien à annuler


def test_after_callback_runs_only_on_success():
    appeles = []
    echec, _, _, _ = lancer([PERSONNE] * 6)
    echec.start("Léa", apres=appeles.append)
    echec.join()
    assert appeles == []
    reco = FauxReconnaisseur([OK, OK, OK])
    reussi = Enrollment(get_frame=lambda: object(), recognizer=reco, poses=TROIS, sleep=lambda s: None)
    reussi.start("Léa", apres=appeles.append)
    reussi.join()
    assert appeles == ["Léa"] and reussi.status()["etat"] == "termine"


def test_failing_after_callback_does_not_fail_the_enrollment():
    def casse(nom):
        raise OSError("disque plein")

    reco = FauxReconnaisseur([OK, OK, OK])
    enrolement = Enrollment(get_frame=lambda: object(), recognizer=reco, poses=TROIS, sleep=lambda s: None)
    enrolement.start("Léa", apres=casse)
    enrolement.join()
    assert enrolement.status()["etat"] == "termine"


def test_default_poses_cover_front_sides_up_down_and_are_short_enough_to_say():
    assert len(POSES) == 6
    assert all(len(pose.dire) < 90 and pose.titre for pose in POSES)
