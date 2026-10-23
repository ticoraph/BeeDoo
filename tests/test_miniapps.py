import random

import pytest

pytest.importorskip("certifi")

from beedoo.miniapps import toutes  # noqa: E402
from beedoo.miniapps.base import Contexte, MiniApp, Reponse, contient, normaliser  # noqa: E402
from beedoo.miniapps.routeur import REPONSE_NON, Routeur  # noqa: E402
from beedoo.miniapps.toto import BLAGUES, Toto  # noqa: E402
from beedoo.settings import Settings  # noqa: E402


def contexte(**kwargs) -> Contexte:
    return Contexte(settings=Settings(**kwargs))


def test_normaliser_ignores_case_accents_and_punctuation():
    assert normaliser("  Quel TEMPS, demain ?! ") == "quel temps demain"
    assert normaliser("Météo à Noël") == "meteo a noel"
    assert normaliser("Qu'est-ce qu'il fait") == "qu est ce qu il fait"


def test_contient_matches_whole_words_only():
    assert contient("tu peux rire un peu", ("rire",))
    assert not contient("il va sourire", ("rire",))
    assert contient("va t il pleuvoir demain", ("va t il pleuvoir",))
    assert contient("fais moi rire", ("fais moi rire",))
    assert not contient("", ("blague",))


class Fausse(MiniApp):
    nom, titre = "fausse", "Fausse"
    mots_surs = ("abracadabra",)
    mots_vagues = ("magie",)
    proposition = "Tu veux de la magie ?"

    def __init__(self):
        self.appels = 0

    def repondre(self, texte, contexte):
        self.appels += 1
        return Reponse(("Pouf !",))


def test_sure_keyword_answers_at_once():
    app = Fausse()
    routeur = Routeur([app])
    assert routeur.router("Abracadabra !", contexte()).parties == ("Pouf !",) and app.appels == 1


def test_unknown_sentence_goes_to_free_conversation():
    assert Routeur([Fausse()]).router("Il fait nuit", contexte()) is None


def test_vague_keyword_asks_then_yes_launches():
    app = Fausse()
    routeur = Routeur([app])
    assert routeur.router("j'aime la magie", contexte()).parties == ("Tu veux de la magie ?",)
    assert app.appels == 0
    assert routeur.router("Oui, vas-y !", contexte()).parties == ("Pouf !",) and app.appels == 1


def test_vague_keyword_then_no_or_other_topic():
    routeur = Routeur([Fausse()])
    routeur.router("la magie", contexte())
    assert routeur.router("Non merci", contexte()) == REPONSE_NON
    routeur.router("la magie", contexte())
    assert routeur.router("Il fait beau aujourd'hui", contexte()) is None  # autre sujet : la proposition tombe
    assert routeur.router("oui", contexte()) is None  # et un « oui » plus tard ne relance rien


def test_oui_without_proposal_does_nothing():
    app = Fausse()
    assert Routeur([app]).router("oui", contexte()) is None and app.appels == 0


def test_disabled_app_is_ignored_even_when_proposed():
    app = Fausse()
    coupees = []
    routeur = Routeur([app], lambda: coupees)
    routeur.router("la magie", contexte())
    coupees.append("fausse")
    assert routeur.router("oui", contexte()) is None
    assert routeur.router("abracadabra", contexte()) is None and app.appels == 0


def test_a_broken_app_does_not_break_the_conversation():
    class Casse(Fausse):
        def repondre(self, texte, contexte):
            raise RuntimeError("bug")

    assert Routeur([Casse()]).router("abracadabra", contexte()) is None


def test_real_registry():
    noms = [app.nom for app in toutes()]
    assert noms == ["toto", "meteo", "heure"]  # pas d'actualités (décision du 2026-10-23)
    assert len(set(noms)) == len(noms)


@pytest.mark.parametrize("phrase,attendu", [
    ("Raconte-moi une blague", "toto"), ("Tu connais Toto ?", "toto"), ("Fais-moi rire !", "toto"),
    ("Quel temps fait-il ?", "meteo"), ("Il va pleuvoir demain ?", "meteo"), ("C'est quoi la météo", "meteo"),
    ("Quelle température il fait", "meteo")])
def test_real_keywords_trigger_the_right_app(phrase, attendu):
    apps = {app.nom: app for app in toutes()}
    routeur = Routeur(list(apps.values()))
    declenchees = []
    for nom, app in apps.items():
        app.repondre = lambda texte, ctx, nom=nom: declenchees.append(nom) or Reponse(("ok",))
    routeur.router(phrase, contexte())
    assert declenchees == [attendu]


@pytest.mark.parametrize("phrase", ["Bonjour BeeDoo", "J'ai mangé une pomme", "Il sourit tout le temps",
                                    "Je suis fatigué", "Il est très gentil"])
def test_ordinary_sentences_are_left_to_the_llm(phrase):
    assert Routeur(toutes()).router(phrase, contexte()) is None


def test_vague_real_keywords_ask_first():
    routeur = Routeur(toutes())
    assert routeur.router("c'est drôle", contexte()).parties == ("Tu veux que je te raconte une blague de Toto ?",)
    assert routeur.router("et dehors ?", contexte()).parties == ("Tu veux que je regarde la météo ?",)


# --- Toto ---
def test_toto_two_parts_and_gesture():
    reponse = Toto(random.Random(1)).repondre("blague", contexte())
    assert len(reponse.parties) == 2 and reponse.geste == "antennes_content"
    assert reponse.parties[0].startswith("Ah, une blague de Toto")


def test_toto_never_repeats_before_the_whole_list_is_told():
    toto = Toto(random.Random(3))
    dites = [toto.repondre("blague", contexte()).parties[1] for _ in range(len(BLAGUES))]
    assert len(set(dites)) == len(BLAGUES)


def test_toto_does_not_repeat_the_last_one_after_a_full_round():
    toto = Toto(random.Random(7))
    derniere = None
    for _ in range(len(BLAGUES) * 3):
        chute = toto.repondre("blague", contexte()).parties[1]
        assert chute != derniere
        derniere = chute


def test_jokes_are_well_formed():
    assert len(BLAGUES) >= 10
    assert len({chute for _, chute in BLAGUES}) == len(BLAGUES)
    assert all(mise.strip() and chute.strip() for mise, chute in BLAGUES)
    assert all("{" not in mise + chute for mise, chute in BLAGUES)
