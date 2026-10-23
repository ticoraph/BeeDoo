import os
from pathlib import Path

import pytest

pytest.importorskip("reachy_mini")

from beedoo.config import Config
from beedoo.settings import Settings
from beedoo.voice import speaker as speaker_module
from beedoo.voice.speaker import Speaker


class FauxMedia:
    def __init__(self):
        self.joue = []
        self.audio = self

    def play_sound(self, chemin):
        assert os.path.exists(chemin)  # le fichier existe pendant la lecture
        self.joue.append(chemin)

    def clear_player(self):
        pass


class FauxRobot:
    def __init__(self):
        self.media = FauxMedia()


@pytest.fixture
def parle(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "cle-de-test-openai")
    config = Config.load(env_file=tmp_path / "absent.env")
    monkeypatch.setattr(speaker_module, "synthesize", lambda *a, **k: b"mp3")
    monkeypatch.setattr("reachy_mini.media.gstreamer_utils.audio_duration_seconds", lambda chemin: 0.01)
    robot = FauxRobot()
    settings = Settings()
    return Speaker(robot, config, settings), robot, settings


def test_speaks_then_removes_temp_file(parle):
    speaker, robot, _ = parle
    assert speaker.say("Bonjour !")
    assert len(robot.media.joue) == 1
    assert not os.path.exists(robot.media.joue[0])


def test_muted_says_nothing(parle):
    speaker, robot, settings = parle
    settings.muet = True
    assert not speaker.say("Bonjour !")
    assert robot.media.joue == []


def test_synthesis_error_is_not_fatal(parle, monkeypatch):
    speaker, robot, _ = parle

    def echec(*a, **k):
        raise speaker_module.TTSError("OpenAI a répondu 500")

    monkeypatch.setattr(speaker_module, "synthesize", echec)
    assert not speaker.say("Bonjour !")
    assert not speaker.parle


def test_chosen_voice_and_speed_reach_the_synthesis(parle, monkeypatch):
    speaker, robot, settings = parle
    vus = {}

    def faux(config, texte, vitesse=1.0, voix=None, **k):
        vus.update(vitesse=vitesse, voix=voix)
        return b"mp3"

    monkeypatch.setattr(speaker_module, "synthesize", faux)
    settings.vitesse, settings.voix = 1.3, "coral"
    speaker.say("Bonjour")
    assert vus == {"vitesse": 1.3, "voix": "coral"}
    settings.voix = ""
    speaker.say("Bonjour")
    assert vus["voix"] is None  # vide = voix de la configuration
