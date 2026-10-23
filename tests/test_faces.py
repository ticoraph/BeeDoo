import numpy as np
import pytest

from beedoo.vision.faces import FaceStore, best_match, cosine_distance, person_id


def unit(*values):
    v = np.array(values, dtype=float)
    return (v / np.linalg.norm(v)).tolist()


GALLERY = {
    "anna": [unit(1, 0, 0), unit(0.9, 0.2, 0)],
    "bob": [unit(0, 1, 0)],
}


def test_known_person_is_recognized_with_closest_embedding():
    match = best_match(unit(0.95, 0.1, 0), GALLERY, threshold=0.3)
    assert match.person == "anna"
    assert match.margin > 0.5


def test_far_face_is_unknown():
    match = best_match(unit(0, 0, 1), GALLERY, threshold=0.3)
    assert match.person is None and match.reason == "trop_loin"


def test_face_almost_equidistant_from_two_people_is_ambiguous():
    gallery = {"anna": [unit(1, 0, 0)], "bob": [unit(0, 1, 0)]}
    match = best_match(unit(1, 1.05, 0), gallery, threshold=0.6, min_margin=0.05)
    assert match.person is None and match.reason == "ambigu"
    assert match.margin < 0.05


def test_empty_gallery_is_unknown():
    assert best_match(unit(1, 0, 0), {}, threshold=0.3).reason == "aucune_personne"


def test_distance_zero_for_same_vector():
    assert cosine_distance([1, 2, 3], [2, 4, 6]) == pytest.approx(0, abs=1e-9)


def test_person_id_is_safe_for_folder_names():
    assert person_id("Mamie Jéanne") == "mamie-jeanne"
    assert "/" not in person_id("../../etc/passwd") and ".." not in person_id("../../etc/passwd")
    with pytest.raises(ValueError):
        person_id("///")


def test_store_roundtrip_and_forget(tmp_path):
    store = FaceStore(tmp_path)
    assert store.add("Anna", [unit(1, 0, 0)]) == 1
    assert store.add("Anna", [unit(0.9, 0.1, 0)]) == 2
    assert store.people() == ["anna"]
    assert len(store.gallery()["anna"]) == 2
    store.forget("Anna")
    assert store.people() == [] and not (tmp_path / "personnes" / "anna").exists()


def test_embeddings_of_another_model_are_ignored(tmp_path):
    FaceStore(tmp_path, model="ArcFace").add("anna", [unit(1, 0, 0)])
    assert FaceStore(tmp_path, model="Facenet").embeddings("anna") == []


def test_display_name_keeps_accents(tmp_path):
    store = FaceStore(tmp_path)
    store.add("Léa", [unit(1, 0, 0)])
    assert store.people() == ["lea"]
    assert store.display_name("lea") == "Léa"
    store.add("lea", [unit(0.9, 0.1, 0)])  # un deuxième ajout ne change pas le prénom
    assert store.display_name("lea") == "Léa"


def test_rename_moves_person_and_refuses_duplicates(tmp_path):
    store = FaceStore(tmp_path)
    store.add("Léa", [unit(1, 0, 0)])
    store.add("Paul", [unit(0, 1, 0)])
    assert store.rename("lea", "Léane") == "leane"
    assert store.people() == ["leane", "paul"]
    assert store.display_name("leane") == "Léane"
    assert len(store.embeddings("leane")) == 1
    with pytest.raises(ValueError):
        store.rename("leane", "Paul")
    with pytest.raises(KeyError):
        store.rename("absent", "Zoé")
    assert store.rename("paul", "PAUL") == "paul"  # même identifiant : seul l'affichage change
    assert store.display_name("paul") == "PAUL"


def test_recognizer_reports_small_face_without_enrolling(tmp_path, monkeypatch):
    from beedoo.vision import faces
    from beedoo.vision.faces import FaceRecognizer, Visage

    store = FaceStore(tmp_path)
    reco = FaceRecognizer(store, min_face_pixels=60)
    monkeypatch.setattr(faces, "detect_face", lambda *a, **k: Visage(unit(1, 0, 0), 40))
    assert reco.enroll_image("Léa", object()).statut == "trop_petit"
    assert store.people() == []
    assert reco.identify(object()).reason == "trop_petit"
    monkeypatch.setattr(faces, "detect_face", lambda *a, **k: Visage(unit(1, 0, 0), 74))
    lecture = reco.enroll_image("Léa", object())
    assert lecture.statut == "ok" and lecture.taille == 74 and store.people() == ["lea"]
    match = reco.identify(object())
    assert match.person == "lea" and match.taille == 74
    monkeypatch.setattr(faces, "detect_face", lambda *a, **k: None)
    assert reco.identify(object()).reason == "aucun_visage"
    assert reco.enroll_image("Léa", object()).statut == "aucun_visage"
