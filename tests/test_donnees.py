import os
import stat
from datetime import datetime
from pathlib import Path

import pytest

from beedoo.donnees import proteger
from beedoo.memory.store import MemoryStore
from beedoo.settings import Settings
from beedoo.vision.faces import FaceStore


def mode(chemin: Path) -> str:
    return oct(stat.S_IMODE(os.stat(chemin).st_mode))[-3:]


def arbre(racine: Path) -> Path:
    (racine / "personnes" / "lea" / "conversations").mkdir(parents=True)
    (racine / "spikes").mkdir()
    for f in ("personnes/lea/visage.json", "personnes/lea/conversations/a.md", "spikes/voix.wav", "settings.json"):
        (racine / f).write_text("x")
        os.chmod(racine / f, 0o644)
    for d in (racine, racine / "personnes", racine / "personnes" / "lea", racine / "spikes"):
        os.chmod(d, 0o755)
    return racine


def test_everything_becomes_private(tmp_path):
    data = arbre(tmp_path / "data")
    assert proteger(data) == 9  # 4 dossiers + conversations + 4 fichiers
    for chemin in [data, *data.rglob("*")]:
        assert mode(chemin) == ("700" if chemin.is_dir() else "600"), chemin


def test_protection_is_idempotent(tmp_path):
    data = arbre(tmp_path / "data")
    proteger(data)
    assert proteger(data) == 0


def test_missing_path_and_single_file(tmp_path):
    assert proteger(tmp_path / "absent") == 0
    fichier = tmp_path / "f.txt"
    fichier.write_text("x")
    os.chmod(fichier, 0o644)
    assert proteger(fichier) == 1 and mode(fichier) == "600"


def test_symlinks_are_never_followed(tmp_path):
    dehors = tmp_path / "dehors.txt"
    dehors.write_text("x")
    os.chmod(dehors, 0o644)
    data = tmp_path / "data"
    data.mkdir()
    (data / "lien.txt").symlink_to(dehors)
    proteger(data)
    assert mode(dehors) == "644"  # la cible d'un lien n'est pas touchée
    lien_dossier = tmp_path / "lien-data"
    lien_dossier.symlink_to(data)
    assert proteger(lien_dossier) == 0


def test_unwritable_permissions_do_not_crash(tmp_path, monkeypatch):
    data = arbre(tmp_path / "data")

    def refuse(*a, **k):
        raise PermissionError("pas le propriétaire")

    monkeypatch.setattr(os, "chmod", refuse)
    assert proteger(data) == 0


# --- ce qui est écrit ensuite est privé dès la création ---
def test_new_face_data_is_private(tmp_path):
    data = tmp_path / "data"
    FaceStore(data).add("Léa", [[1.0, 0.0]])
    assert mode(data / "personnes" / "lea" / "visage.json") == "600"
    assert mode(data / "personnes" / "lea") == "700" and mode(data / "personnes") == "700" and mode(data) == "700"


def test_new_settings_are_private(tmp_path):
    data = tmp_path / "data"
    Settings(ville="Paris").save(data)
    assert mode(data / "settings.json") == "600" and mode(data) == "700"


def test_new_memory_and_conversations_are_private(tmp_path):
    data = tmp_path / "data"
    memoire = MemoryStore(data)
    memoire.set_consentement("lea", True)
    memoire.ecrire_faits("lea", ["Elle aime les chats."])
    chemin = memoire.enregistrer_conversation("lea", "Léa", [("a b c d", "ok")], datetime(2026, 10, 23, 10, 0))
    assert mode(chemin) == "600" and mode(chemin.parent) == "700"
    assert mode(data / "personnes" / "lea" / "memoire.json") == "600"
    assert mode(data / "personnes" / "lea" / "profil.md") == "600"
    assert mode(data / "personnes" / "lea") == "700" and mode(data) == "700"


def test_enrolling_a_second_person_keeps_everything_private(tmp_path):
    data = tmp_path / "data"
    faces = FaceStore(data)
    faces.add("Léa", [[1.0, 0.0]])
    faces.add("Paul", [[0.0, 1.0]])
    faces.rename("paul", "Pablo")
    for chemin in [data, *data.rglob("*")]:
        assert mode(chemin) == ("700" if chemin.is_dir() else "600"), chemin
