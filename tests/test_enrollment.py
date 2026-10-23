from beedoo.vision.enrollment import Enrollment


class FauxReconnaisseur:
    def __init__(self, ajouts):
        self.ajouts = list(ajouts)
        self.noms = []

    def enroll(self, nom, images):
        self.noms.append(nom)
        return self.ajouts.pop(0)


def lancer(ajouts, frames=None):
    reco = FauxReconnaisseur(ajouts)
    suite = iter(frames if frames is not None else [object()] * len(ajouts))
    enrolement = Enrollment(get_frame=lambda: next(suite), recognizer=reco, total=len(ajouts), interval=0,
                            sleep=lambda s: None)
    assert enrolement.start("Léa")
    enrolement.join()
    return enrolement, reco


def test_success_counts_embeddings():
    enrolement, reco = lancer([1, 1, 0, 1])
    assert enrolement.status() == {"etat": "termine", "fait": 4, "total": 4, "ajoutes": 3}
    assert reco.noms == ["Léa"] * 4
    assert not enrolement.en_cours


def test_failure_when_no_face_found():
    enrolement, _ = lancer([0, 0, 0])
    assert enrolement.status()["etat"] == "echec"


def test_missing_frames_are_skipped():
    enrolement, reco = lancer([1, 1], frames=[None, object()])
    assert enrolement.status()["ajoutes"] == 1
    assert len(reco.noms) == 1


def test_camera_error_does_not_crash():
    def casse():
        raise ConnectionError("caméra")

    enrolement = Enrollment(get_frame=casse, recognizer=FauxReconnaisseur([]), total=2, interval=0,
                            sleep=lambda s: None)
    enrolement.start("Léa")
    enrolement.join()
    assert enrolement.status()["etat"] == "echec" and enrolement.status()["fait"] == 2


def test_second_start_refused_while_running():
    import threading

    porte = threading.Event()
    enrolement = Enrollment(get_frame=lambda: None, recognizer=FauxReconnaisseur([]), total=1, interval=0,
                            sleep=lambda s: porte.wait(2))
    assert enrolement.start("Léa")
    assert not enrolement.start("Paul")
    porte.set()
    enrolement.join()
