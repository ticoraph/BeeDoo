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
from beedoo.memory.store import MemoryStore  # noqa: E402
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

    def reply(self, texte, prenom="inconnu", souvenirs="rien pour l'instant"):
        if self.erreur:
            raise self.erreur
        self.questions.append((texte, prenom))
        self.souvenirs = getattr(self, "souvenirs", []) + [souvenirs]
        return "Salut, ça va bien !"

    def reset(self):
        self.resets += 1

    def memoriser(self, texte, reponse):
        self.memorise = getattr(self, "memorise", []) + [(texte, reponse)]


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
    runtime.memoire = MemoryStore(tmp_path)
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


def test_last_exchange_is_kept_in_memory_then_forgotten(monde):
    runtime, micro, *_, c = monde
    c.tick()
    dire_une_phrase(c, micro)
    assert runtime.echange == {"entendu": "Bonjour BeeDoo, ça va ?", "dit": "Salut, ça va bien !"}
    runtime.vision.lecture["statut"] = "aucun_visage"
    c._clock.t += conv.ABSENCE + 1
    c.tick()
    assert runtime.echange is None


# --- mini-applications dans la conversation ---
from beedoo.miniapps.base import MiniApp, Reponse  # noqa: E402
from beedoo.miniapps.routeur import Routeur  # noqa: E402


class Blague(MiniApp):
    nom, titre = "blague", "Blague"
    mots_surs = ("blague",)
    proposition = "Une blague ?"

    def repondre(self, texte, contexte):
        return Reponse(("Mise en place.", "Chute !"), geste="antennes_content")


class FauxGestes:
    def __init__(self):
        self.joues = []

    def play(self, nom):
        self.joues.append(nom)
        return True


@pytest.fixture
def monde_apps(monde):
    runtime, micro, chat, horloge, entendu, c = monde
    runtime.gestes = FauxGestes()
    runtime.miniapps = [Blague()]
    c._routeur = Routeur(runtime.miniapps, lambda: runtime.settings.miniapps_desactivees)
    return runtime, micro, chat, entendu, c


def test_miniapp_answers_in_two_parts_without_calling_the_llm(monde_apps):
    runtime, micro, chat, entendu, c = monde_apps
    entendu["texte"] = "Raconte-moi une blague !"
    c.tick()
    dire_une_phrase(c, micro)
    assert chat.questions == []  # le LLM n'a pas été sollicité
    assert runtime.speaker.dit == ["Mise en place.", "Chute !"]
    assert runtime.gestes.joues == ["antennes_content"]
    assert runtime.echange["dit"] == "Mise en place. Chute !"
    assert chat.memorise == [("Raconte-moi une blague !", "Mise en place. Chute !")]  # le LLM s'en souviendra
    assert runtime.machine.state == State.ECOUTE


def test_gesture_comes_with_the_last_part_only(monde_apps):
    runtime, micro, chat, entendu, c = monde_apps
    ordre = []
    runtime.gestes.play = lambda nom: ordre.append(("geste", nom))
    dit = runtime.speaker.dit

    class Trace(FausseVoix):
        def say(self, texte):
            ordre.append(("dit", texte))
            return True

    runtime.speaker = Trace(runtime)
    entendu["texte"] = "une blague"
    c.tick()
    dire_une_phrase(c, micro)
    assert ordre == [("dit", "Mise en place."), ("geste", "antennes_content"), ("dit", "Chute !")]


def test_ordinary_sentence_still_goes_to_the_llm(monde_apps):
    runtime, micro, chat, entendu, c = monde_apps
    c.tick()
    dire_une_phrase(c, micro)  # « Bonjour BeeDoo, ça va ? »
    assert len(chat.questions) == 1 and runtime.speaker.dit == ["Salut, ça va bien !"]


def test_disabled_miniapp_falls_back_to_the_llm(monde_apps):
    runtime, micro, chat, entendu, c = monde_apps
    runtime.settings.miniapps_desactivees = ["blague"]
    entendu["texte"] = "une blague"
    c.tick()
    dire_une_phrase(c, micro)
    assert len(chat.questions) == 1


def test_proposal_is_forgotten_when_the_conversation_ends(monde_apps):
    runtime, micro, chat, entendu, c = monde_apps
    c._routeur._en_attente = runtime.miniapps[0]
    c.tick()
    runtime.vision.lecture["statut"] = "aucun_visage"
    c._clock.t += conv.ABSENCE + 1
    c.tick()
    assert c._routeur._en_attente is None


# --- mémoire (phase 8) ---
from datetime import datetime  # noqa: E402


@pytest.fixture
def monde_memoire(monde, monkeypatch):
    runtime, micro, chat, horloge, entendu, c = monde
    appels = []
    monkeypatch.setattr(conv.extraction, "mettre_a_jour",
                        lambda config, memoire, pid, tours: appels.append((pid, list(tours))))
    c._maintenant = lambda: datetime(2026, 10, 23, 15, 30)
    c._debut_conv = c._maintenant()
    return runtime, micro, chat, horloge, entendu, c, appels


def finir(c):
    c._terminer()
    for fil in c._consolidations:
        fil.join(5)


def test_without_consent_nothing_is_remembered_nor_used(monde_memoire, tmp_path):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.memoire.ecrire_faits("lea", ["Sa fille s'appelle Anna."])  # présent sur le disque, mais pas de consentement
    c.tick()
    dire_une_phrase(c, micro)
    assert chat.souvenirs == ["rien pour l'instant"]
    finir(c)
    assert appels == [] and runtime.memoire.conversations("lea") == []


def test_with_consent_memories_reach_the_llm_and_conversation_is_saved(monde_memoire):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.memoire.set_consentement("lea", True)
    runtime.memoire.ecrire_faits("lea", ["Sa fille s'appelle Anna."])
    c.tick()
    dire_une_phrase(c, micro)
    assert chat.souvenirs == ["- Sa fille s'appelle Anna."]
    finir(c)
    assert runtime.memoire.conversations("lea") == ["2026-10-23_1530"]
    texte = (runtime.memoire.root / "lea" / "conversations" / "2026-10-23_1530.md").read_text()
    assert "**Léa** : Bonjour BeeDoo, ça va ?" in texte and "**BeeDoo** : Salut, ça va bien !" in texte
    assert appels == [("lea", [("Bonjour BeeDoo, ça va ?", "Salut, ça va bien !")])]


def test_conversation_is_consolidated_once_only(monde_memoire):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.memoire.set_consentement("lea", True)
    c.tick()
    dire_une_phrase(c, micro)
    finir(c)
    finir(c)
    assert len(appels) == 1 and len(runtime.memoire.conversations("lea")) == 1


def test_stop_saves_the_running_conversation(monde_memoire):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.memoire.set_consentement("lea", True)
    c.tick()
    dire_une_phrase(c, micro)
    c.stop()  # l'application s'arrête en pleine conversation
    assert len(appels) == 1 and runtime.memoire.conversations("lea") == ["2026-10-23_1530"]


def test_unknown_visitor_gets_no_memories_and_leaves_no_trace(monde_memoire):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.memoire.set_consentement("lea", True)
    runtime.memoire.ecrire_faits("lea", ["Sa fille s'appelle Anna."])
    c.tick()
    runtime.vision.lecture["statut"] = "inconnu"  # Léa est partie, un visiteur parle
    horloge.t += conv.RECONNU_RECEMMENT + 1
    dire_une_phrase(c, micro)
    assert chat.souvenirs == ["rien pour l'instant"] and chat.questions[0][1] == "inconnu"
    finir(c)
    assert appels == [] and runtime.memoire.conversations("lea") == []


def test_other_person_never_hears_what_the_first_one_said(monde_memoire):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.faces.add("Paul", [[0.0, 1.0]])
    for pid in ("lea", "paul"):
        runtime.memoire.set_consentement(pid, True)
    runtime.memoire.ecrire_faits("lea", ["Sa fille s'appelle Anna."])
    runtime.memoire.ecrire_faits("paul", ["Il aime la pêche."])
    c.tick()
    dire_une_phrase(c, micro)  # Léa parle
    runtime.vision.lecture.update(personne="paul")  # Paul prend sa place
    horloge.t += 1
    dire_une_phrase(c, micro)
    assert chat.souvenirs == ["- Sa fille s'appelle Anna.", "- Il aime la pêche."]
    assert chat.resets >= 1  # l'historique de Léa a été oublié avant de parler à Paul
    assert chat.questions[1][1] == "Paul"
    finir(c)
    assert sorted(pid for pid, _ in appels) == ["lea", "paul"]
    assert all(len(t) == 1 for _, t in appels)  # chacun n'a que ses propres paroles


def test_consent_withdrawn_stops_extraction_and_later_exchanges(monde_memoire):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.memoire.set_consentement("lea", True)
    c.tick()
    dire_une_phrase(c, micro)
    runtime.memoire.set_consentement("lea", False)
    dire_une_phrase(c, micro)  # une deuxième phrase, après le retrait
    finir(c)
    assert appels == []  # plus de faits retenus
    assert len(runtime.memoire.conversations("lea")) == 1  # ce qui était déjà écrit reste (« Effacer » est à part)
    texte = (runtime.memoire.root / "lea" / "conversations" / "2026-10-23_1530.md").read_text()
    assert texte.count("**Léa**") == 1  # la phrase d'après le retrait n'est pas enregistrée


def test_person_erased_during_conversation_is_not_resurrected(monde_memoire, tmp_path):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.memoire.set_consentement("lea", True)
    c.tick()
    dire_une_phrase(c, micro)
    runtime.faces.forget("lea")  # effacée depuis la page
    finir(c)
    assert appels == [] and not (tmp_path / "personnes" / "lea").exists()


def test_memory_failure_never_breaks_the_conversation(monde_memoire, monkeypatch):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.memoire.set_consentement("lea", True)

    def casse(*a, **k):
        raise conv.LLMError("OpenAI a répondu 500")

    monkeypatch.setattr(conv.extraction, "mettre_a_jour", casse)
    c.tick()
    dire_une_phrase(c, micro)
    finir(c)
    assert runtime.machine.state == State.VEILLE
    assert runtime.memoire.conversations("lea") == ["2026-10-23_1530"]  # la conversation est quand même gardée


def test_conversation_is_on_disk_right_after_each_exchange_in_one_single_file(monde_memoire):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.memoire.set_consentement("lea", True)
    c.tick()
    dire_une_phrase(c, micro)
    assert runtime.memoire.conversations("lea") == ["2026-10-23_1530"]  # déjà là, la conversation n'est pas finie
    assert runtime.machine.state == State.ECOUTE
    entendu["texte"] = "Ma fille s'appelle Anna"
    dire_une_phrase(c, micro)
    assert runtime.memoire.conversations("lea") == ["2026-10-23_1530"]  # même fichier, complété
    texte = (runtime.memoire.root / "lea" / "conversations" / "2026-10-23_1530.md").read_text()
    assert texte.count("**Léa**") == 2 and "Ma fille s'appelle Anna" in texte


def test_facts_are_retained_after_a_silence_without_waiting_for_the_end(monde_memoire):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.memoire.set_consentement("lea", True)
    c.tick()
    dire_une_phrase(c, micro)
    c.tick()
    assert appels == []  # trop tôt : la personne vient de parler
    horloge.t += conv.PAUSE_EXTRACTION + 1
    c.tick()
    for fil in c._consolidations:
        fil.join(5)
    assert len(appels) == 1 and appels[0][1] == [("Bonjour BeeDoo, ça va ?", "Salut, ça va bien !")]
    assert runtime.machine.state == State.ECOUTE  # la conversation continue
    c.tick()
    assert len(appels) == 1  # et on ne recommence pas tant qu'il n'y a rien de nouveau


def test_only_new_exchanges_are_examined_each_time(monde_memoire):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    runtime.memoire.set_consentement("lea", True)
    c.tick()
    dire_une_phrase(c, micro)
    horloge.t += conv.PAUSE_EXTRACTION + 1
    c.tick()
    for fil in c._consolidations:
        fil.join(5)
    entendu["texte"] = "J'ai un chat qui s'appelle Pompon"
    dire_une_phrase(c, micro)
    finir(c)
    assert [len(t) for _, t in appels] == [1, 1]
    assert appels[1][1][0][0] == "J'ai un chat qui s'appelle Pompon"


def test_memory_status_for_the_page(monde_memoire):
    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    c.tick()
    assert c.info_memoire() == {"etat": "desactivee"}  # pas de consentement : la page le dit
    runtime.memoire.set_consentement("lea", True)
    assert c.info_memoire()["etat"] == "attente"
    dire_une_phrase(c, micro)
    info = c.info_memoire()
    assert info["etat"] == "enregistre" and info["phrases"] == 1 and info["en_attente"] == 1
    assert info["pause"] == conv.PAUSE_EXTRACTION
    horloge.t += conv.RECONNU_RECEMMENT + 1  # on ne sait plus qui est là
    assert c.info_memoire() == {"etat": "personne"}


def test_status_reports_last_result_counts_only(monde_memoire, monkeypatch):
    from beedoo.memory.extraction import Resultat

    runtime, micro, chat, horloge, entendu, c, appels = monde_memoire
    monkeypatch.setattr(conv.extraction, "mettre_a_jour", lambda *a, **k: Resultat(2, 1, 0))
    runtime.memoire.set_consentement("lea", True)
    c.tick()
    dire_une_phrase(c, micro)
    finir(c)
    assert c.info_memoire()["dernier"] == {"ajoutes": 2, "retires": 1, "rejetes": 0}
