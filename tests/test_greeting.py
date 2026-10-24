import json
import random
from pathlib import Path

import pytest

pytest.importorskip("reachy_mini")

from beedoo.config import Config
from beedoo.greeting import PHRASES, Salutation, salutation_personnalisee
from beedoo.runtime import Runtime
from beedoo.settings import Settings
from beedoo.state import State
from beedoo.vision.faces import FaceStore
from beedoo.vision.greeter import INCONNU, SALUE, Event


class FauxGestes:
    def __init__(self):
        self.joues = []

    def play(self, nom):
        self.joues.append(nom)
        return True


class FausseVoix:
    def __init__(self, machine):
        self.dit = []
        self.machine = machine
        self.etats = []

    def say(self, texte):
        self.etats.append(self.machine.state)
        self.dit.append(texte)
        return True


@pytest.fixture
def monde(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BEEDOO_DATA_DIR", str(tmp_path))
    runtime = Runtime(config=Config.load(env_file=tmp_path / "absent.env"), settings=Settings())
    runtime.faces = FaceStore(tmp_path)
    runtime.faces.add("Léa", [[1.0, 0.0]])
    runtime.gestes = FauxGestes()
    runtime.speaker = FausseVoix(runtime.machine)
    return runtime, Salutation(runtime, rng=random.Random(1))


def test_known_person_gets_gesture_and_spoken_name(monde):
    runtime, salutation = monde
    salutation.on_event(Event(SALUE, "lea"))
    assert runtime.gestes.joues == ["antennes_content"]
    assert len(runtime.speaker.dit) == 1 and "Léa" in runtime.speaker.dit[0]
    assert runtime.speaker.etats == [State.PAROLE]  # parlait pendant l'état « parole »
    assert runtime.machine.state == State.VEILLE  # et revient en veille


def test_unknown_face_is_silent(monde):
    runtime, salutation = monde
    salutation.on_event(Event(INCONNU))
    assert runtime.speaker.dit == [] and runtime.gestes.joues == []


def test_no_greeting_while_a_sentence_is_being_processed(monde):
    runtime, salutation = monde
    runtime.machine.go(State.ECOUTE)
    runtime.machine.go(State.REFLEXION)
    salutation.on_event(Event(SALUE, "lea"))
    assert runtime.speaker.dit == [] and runtime.machine.state == State.REFLEXION


def test_greeting_while_listening_returns_to_listening(monde):
    runtime, salutation = monde
    runtime.machine.go(State.ECOUTE)
    salutation.on_event(Event(SALUE, "lea"))
    assert len(runtime.speaker.dit) == 1 and runtime.speaker.etats == [State.PAROLE]
    assert runtime.machine.state == State.ECOUTE


def test_returns_to_veille_even_if_speaking_fails(monde):
    runtime, salutation = monde

    def casse(texte):
        raise RuntimeError("haut-parleur")

    runtime.speaker.say = casse
    with pytest.raises(RuntimeError):
        salutation.on_event(Event(SALUE, "lea"))
    assert runtime.machine.state == State.VEILLE


def test_phrases_all_use_the_name():
    assert all("{nom}" in phrase for phrase in PHRASES)


def test_custom_greeting_replaces_the_usual_one(monde, tmp_path):
    runtime, salutation = monde
    (tmp_path / "salutations.json").write_text(json.dumps({"lea": "Phrase secrète de test !"}), encoding="utf-8")
    salutation.on_event(Event(SALUE, "lea"))
    assert runtime.speaker.dit == ["Phrase secrète de test !"]
    assert runtime.gestes.joues == ["antennes_content"]


def test_custom_greeting_only_for_the_right_person(tmp_path):
    (tmp_path / "salutations.json").write_text(json.dumps({"lea": "Coucou spécial"}), encoding="utf-8")
    assert salutation_personnalisee(tmp_path, "lea") == "Coucou spécial"
    assert salutation_personnalisee(tmp_path, "jeanne") is None


@pytest.mark.parametrize("contenu", ["pas du json", "[1, 2]", '{"lea": 3}', '{"lea": "  "}'])
def test_broken_custom_greeting_file_falls_back(tmp_path, contenu):
    (tmp_path / "salutations.json").write_text(contenu, encoding="utf-8")
    assert salutation_personnalisee(tmp_path, "lea") is None


def test_missing_custom_greeting_file_falls_back(tmp_path):
    assert salutation_personnalisee(tmp_path, "lea") is None
