from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("reachy_mini")
pytest.importorskip("certifi")

from beedoo import conversation as conv  # noqa: E402
from beedoo.config import Config  # noqa: E402
from beedoo.llm.chat import LLMError, NE_SAIT_PAS  # noqa: E402
from beedoo.runtime import Runtime  # noqa: E402
from beedoo.settings import Settings  # noqa: E402
from beedoo.state import State  # noqa: E402
from beedoo.vision.faces import FaceStore  # noqa: E402
from beedoo.voice.stt import STTError  # noqa: E402

RATE = 16000
PAS = RATE // 10  # chunks de 0,1 s


class FauxMicro:
    def __init__(self):
        self.enregistre = False
        self.demarrages = 0
        self.file = []
        self.parole = False

    def start_recording(self):
        self.enregistre = True
        self.demarrages += 1
        self.file.clear()

    def stop_recording(self):
        self.enregistre = False

    def get_input_audio_samplerate(self):
        return RATE

    def get_audio_sample(self):
        return self.file.pop(0) if self.file else None

    def get_DoA(self):
        return (1.5, self.parole)


class FausseVision:
    def __init__(self):
        self.lecture = {"statut": "reconnu", "taille": 100, "personne": "lea", "age": 0.5}

    def status(self):
        return dict(self.lecture)


class FausseVoix:
    parle = False

    def __init__(self, runtime):
        self.runtime = runtime
        self.dit = []
        self.etats = []

    def say(self, texte):
        self.etats.append(self.runtime.machine.state)
        self.dit.append(texte)
        return True


class FauxChat:
    def __init__(self):
        self.questions = []
        self.erreur = None
        self.resets = 0

    def reply(self, texte, prenom="inconnu"):
        if self.erreur:
            raise self.erreur
        self.questions.append((texte, prenom))
        return "Salut, ça va bien !"

    def reset(self):
        self.resets += 1


class Horloge:
    t = 100.0

    def __call__(self):
        return self.t


@pytest.fixture
def monde(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BEEDOO_DATA_DIR", str(tmp_path))
    runtime = Runtime(config=Config.load(env_file=tmp_path / "absent.env"), settings=Settings())
    runtime.faces = FaceStore(tmp_path)
    runtime.faces.add("Léa", [[1.0, 0.0]])
    runtime.vision = FausseVision()
    runtime.speaker = FausseVoix(runtime)
    micro, chat, horloge = FauxMicro(), FauxChat(), Horloge()
    entendu = {"texte": "Bonjour BeeDoo, ça va ?", "n": 0}

    def transcrire(audio, rate):
        entendu["n"] += 1
        if isinstance(entendu["texte"], Exception):
            raise entendu["texte"]
        return entendu["texte"]

    c = conv.Conversation(runtime, micro, transcrire, chat, clock=horloge)
    c._stop.wait = lambda t=None: None  # pas d'attente réelle dans les tests
    return runtime, micro, chat, horloge, entendu, c


def parler(c, micro, secondes, parole):
    micro.parole = parole
    for _ in range(round(secondes * 10)):
        micro.file.append(np.full((PAS, 2), 0.1 if parole else 0.0, dtype=np.float32))
        c.tick()


def dire_une_phrase(c, micro):
    parler(c, micro, 1.0, True)
    parler(c, micro, 1.2, False)


def test_microphone_stays_off_without_a_known_person(monde):
    runtime, micro, *_, c = monde
    runtime.vision.lecture["statut"] = "aucun_visage"
    for _ in range(5):
        c.tick()
    assert micro.demarrages == 0 and runtime.machine.state == State.VEILLE
    runtime.vision.lecture["statut"] = "inconnu"  # un inconnu ne déclenche pas non plus l'écoute
    c.tick()
    assert micro.demarrages == 0


def test_known_person_turns_microphone_on(monde):
    runtime, micro, *_, c = monde
    c.tick()
    assert micro.enregistre and runtime.machine.state == State.ECOUTE


def test_full_turn_transcribes_asks_llm_and_speaks(monde):
    runtime, micro, chat, _, entendu, c = monde
    c.tick()
    dire_une_phrase(c, micro)
    assert chat.questions == [("Bonjour BeeDoo, ça va ?", "Léa")]
    assert runtime.speaker.dit == ["Salut, ça va bien !"]
    assert runtime.speaker.etats == [State.PAROLE]
    assert runtime.machine.state == State.ECOUTE  # prêt pour la phrase suivante


def test_noise_without_a_sentence_triggers_nothing(monde):
    runtime, micro, chat, _, entendu, c = monde
    c.tick()
    parler(c, micro, 2.0, False)
    assert entendu["n"] == 0 and chat.questions == []


def test_invented_transcription_is_ignored_silently(monde):
    runtime, micro, chat, _, entendu, c = monde
    entendu["texte"] = "嘶嘶嘶"
    c.tick()
    dire_une_phrase(c, micro)
    assert entendu["n"] == 1 and chat.questions == [] and runtime.speaker.dit == []
    assert runtime.machine.state == State.ECOUTE


def test_transcription_error_is_not_fatal(monde):
    runtime, micro, chat, _, entendu, c = monde
    entendu["texte"] = STTError("OpenAI a répondu 500")
    c.tick()
    dire_une_phrase(c, micro)
    assert chat.questions == [] and runtime.machine.state == State.ECOUTE


def test_llm_failure_makes_beedoo_ask_to_repeat(monde):
    runtime, micro, chat, *_, c = monde
    chat.erreur = LLMError("OpenAI a répondu 429")
    c.tick()
    dire_une_phrase(c, micro)
    assert runtime.speaker.dit == [NE_SAIT_PAS] and runtime.machine.state == State.ECOUTE


def test_conversation_ends_after_absence_and_forgets(monde):
    runtime, micro, chat, horloge, _, c = monde
    c.tick()
    runtime.vision.lecture["statut"] = "aucun_visage"
    horloge.t += conv.ABSENCE - 1
    c.tick()
    assert runtime.machine.state == State.ECOUTE  # on tolère une courte absence (tête tournée)
    horloge.t += 2
    c.tick()
    assert runtime.machine.state == State.VEILLE and not micro.enregistre and chat.resets == 1


def test_mute_stops_microphone_at_once(monde):
    runtime, micro, chat, *_, c = monde
    c.tick()
    runtime.settings.muet = True
    c.tick()
    assert not micro.enregistre and runtime.machine.state == State.VEILLE
    c.tick()
    assert micro.demarrages == 1  # tant qu'il est muet, il ne se rallume pas


def test_audio_is_discarded_while_beedoo_speaks(monde):
    runtime, micro, chat, _, entendu, c = monde
    c.tick()
    runtime.machine.go(State.PAROLE)  # salutation par exemple
    parler(c, micro, 2.0, True)
    runtime.machine.go(State.ECOUTE)
    parler(c, micro, 1.2, False)
    assert entendu["n"] == 0  # ce qui s'est dit pendant la parole n'est pas devenu une phrase


def test_stale_camera_reading_is_not_trusted(monde):
    runtime, micro, *_, c = monde
    runtime.vision.lecture["age"] = 60.0
    c.tick()
    assert micro.demarrages == 0
