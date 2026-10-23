from datetime import datetime

import pytest

pytest.importorskip("certifi")

from beedoo.miniapps import toutes  # noqa: E402
from beedoo.miniapps.base import Contexte  # noqa: E402
from beedoo.miniapps.heure import HeureDate, date_parlee, heure_parlee  # noqa: E402
from beedoo.miniapps.routeur import Routeur  # noqa: E402
from beedoo.settings import Settings  # noqa: E402


def a(h, m=0, jour=(2026, 10, 22)):
    return datetime(*jour, h, m)


@pytest.mark.parametrize("heure,attendu", [
    ((0, 0), "minuit"), ((0, 30), "minuit et demi"), ((0, 50), "une heure moins dix du matin"),
    ((1, 5), "une heure cinq du matin"), ((7, 15), "7 heures et quart du matin"), ((9, 0), "9 heures du matin"),
    ((11, 45), "midi moins le quart"), ((11, 50), "midi moins dix"), ((12, 0), "midi"),
    ((12, 30), "midi et demi"), ((12, 50), "une heure moins dix de l'après-midi"),
    ((13, 10), "une heure 10 de l'après-midi"), ((15, 30), "3 heures et demie de l'après-midi"),
    ((17, 55), "6 heures moins cinq du soir"), ((18, 59), "7 heures moins une du soir"),
    ((20, 40), "9 heures moins vingt du soir"), ((23, 0), "11 heures du soir"), ((23, 50), "minuit moins dix"),
    ((22, 35), "10 heures 35 du soir")])
def test_time_is_said_like_a_person(heure, attendu):
    assert heure_parlee(a(*heure)) == attendu


def test_every_minute_of_the_day_has_a_phrase():
    for h in range(24):
        for m in range(60):
            texte = heure_parlee(a(h, m))
            assert texte and "  " not in texte and "None" not in texte


def test_date_in_french_regardless_of_system_language():
    assert date_parlee(a(10)) == "jeudi 22 octobre 2026"
    assert date_parlee(datetime(2027, 3, 1)) == "lundi premier mars 2027"
    assert date_parlee(datetime(2026, 2, 28)) == "samedi 28 février 2026"


def reponse(phrase, moment=None):
    contexte = Contexte(settings=Settings(), maintenant=lambda: moment or a(15, 30))
    from beedoo.miniapps.base import normaliser

    return HeureDate().repondre(normaliser(phrase), contexte).parties[0]


def test_time_question():
    assert reponse("Quelle heure est-il ?") == "Il est 3 heures et demie de l'après-midi."
    assert reponse("Tu as l'heure ?") == "Il est 3 heures et demie de l'après-midi."


def test_date_questions():
    assert reponse("On est quel jour ?") == "Nous sommes le jeudi 22 octobre 2026."
    assert reponse("Quelle est la date d'aujourd'hui ?") == "Nous sommes le jeudi 22 octobre 2026."
    assert reponse("On est le combien ?") == "Nous sommes le jeudi 22 octobre 2026."


def test_month_and_year_questions():
    assert reponse("Quel mois on est ?") == "Nous sommes en octobre."
    assert reponse("En quelle année on est ?") == "Nous sommes en 2026."


def test_both_at_once():
    assert reponse("Quel jour et quelle heure ?") == (
        "Nous sommes le jeudi 22 octobre 2026. Il est 3 heures et demie de l'après-midi.")


@pytest.mark.parametrize("phrase", ["Je suis à l'heure", "Il a une heure de retard", "C'est l'heure de manger",
                                    "J'ai passé une bonne journée", "Mon jour préféré est dimanche"])
def test_ordinary_sentences_do_not_trigger_it(phrase):
    assert Routeur([HeureDate()]).router(phrase, Contexte(settings=Settings())) is None


@pytest.mark.parametrize("phrase", ["Quelle heure il est ?", "Dis-moi quel jour on est", "Il est quelle heure ?",
                                    "Quelle heure est-il maintenant", "on est le combien aujourd'hui"])
def test_natural_phrasings_trigger_it(phrase):
    assert Routeur([HeureDate()]).router(phrase, Contexte(settings=Settings())) is not None


def test_registered_and_independent_of_the_network():
    assert [app.nom for app in toutes()] == ["toto", "meteo", "heure"]
    contexte = Contexte(settings=Settings(), http_json=lambda url: (_ for _ in ()).throw(AssertionError("réseau")))
    assert HeureDate().repondre("quelle heure", contexte).parties
