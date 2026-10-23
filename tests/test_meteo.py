import pytest

pytest.importorskip("certifi")

from beedoo.miniapps import meteo  # noqa: E402
from beedoo.miniapps.base import Contexte  # noqa: E402
from beedoo.miniapps.http import ReseauIndisponible  # noqa: E402
from beedoo.settings import Settings  # noqa: E402

PREVISIONS = {
    "current": {"temperature_2m": 14.4, "weather_code": 3},
    "daily": {"weather_code": [61, 2], "temperature_2m_min": [9.2, -2.6], "temperature_2m_max": [15.1, 1.2],
              "precipitation_probability_max": [80, 10]},
}
LIEU = {"results": [{"latitude": 48.85, "longitude": 2.35, "name": "Ville"}]}


def faux_http(*reponses):
    """Renvoie les réponses dans l'ordre (lieu, puis prévisions) et note les adresses demandées."""
    vues, suite = [], iter(reponses)

    def get(url):
        vues.append(url)
        reponse = next(suite)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse

    get.vues = vues
    return get


def ctx(http, ville="Ville"):
    return Contexte(settings=Settings(ville=ville), http_json=http)


def test_degrees_are_spoken_naturally():
    assert meteo.degres(14.4) == "14 degrés"
    assert meteo.degres(1) == "1 degré" and meteo.degres(0.2) == "0 degré"
    assert meteo.degres(-2.6) == "moins 3 degrés" and meteo.degres(-1) == "moins 1 degré"
    assert meteo.entre(-2.6, 1.2) == "entre moins 3 et 1 degré"


def test_today_sentence_with_rain_advice():
    assert meteo.phrase(PREVISIONS, demain=False) == (
        "Dehors, il fait 14 degrés. Le ciel est couvert. Aujourd'hui, il fera entre 9 et 15 degrés. "
        "Prends ton parapluie !")


def test_tomorrow_sentence_with_cold_advice():
    assert meteo.phrase(PREVISIONS, demain=True) == (
        "Demain, il fera entre moins 3 et 1 degré. Il y a quelques nuages. Mets ton gros manteau !")


@pytest.mark.parametrize("code,maxi,proba,attendu", [
    (95, 20, 0, "Reste bien au chaud à la maison."), (63, 20, 0, "Prends ton parapluie !"),
    (2, 20, 70, "Prends ton parapluie !"), (73, 0, 0, "Mets ton gros manteau !"),
    (0, 31, 0, "Il fait chaud, pense à boire de l'eau !"), (1, 18, 10, "")])
def test_advice(code, maxi, proba, attendu):
    assert meteo.conseil(code, maxi, proba) == attendu


def test_sky_phrases_are_short_sentences():
    for code, texte in meteo.CIEL.items():
        assert texte.endswith(".") and len(texte) < 60, code


def test_full_flow_asks_geocoding_then_forecast_and_says_it():
    http = faux_http(LIEU, PREVISIONS)
    reponse = meteo.Meteo().repondre("quel temps fait il", ctx(http))
    assert "Dehors, il fait 14 degrés" in reponse.parties[0]
    assert "geocoding-api.open-meteo.com" in http.vues[0] and "name=Ville" in http.vues[0]
    assert "latitude=48.85" in http.vues[1] and "forecast_days=2" in http.vues[1]


def test_demain_in_the_sentence_gives_tomorrow():
    reponse = meteo.Meteo().repondre("quel temps demain", ctx(faux_http(LIEU, PREVISIONS)))
    assert reponse.parties[0].startswith("Demain")


def test_demain_must_be_a_whole_word():
    reponse = meteo.Meteo().repondre("quel temps fait il apres demainxyz", ctx(faux_http(LIEU, PREVISIONS)))
    assert reponse.parties[0].startswith("Dehors")


def test_no_city_configured_asks_for_it_without_any_network_call():
    http = faux_http()
    reponse = meteo.Meteo().repondre("meteo", ctx(http, ville=""))
    assert "réglages" in reponse.parties[0] and http.vues == []


def test_unknown_city():
    reponse = meteo.Meteo().repondre("meteo", ctx(faux_http({"results": None})))
    assert "ne trouve pas ta ville" in reponse.parties[0]


@pytest.mark.parametrize("panne", [ReseauIndisponible("URLError"), {"daily": {}}, {"current": None, "daily": None}])
def test_network_or_data_problems_give_a_kind_sentence(panne):
    reponse = meteo.Meteo().repondre("meteo", ctx(faux_http(LIEU, panne)))
    assert "Internet ne marche pas bien" in reponse.parties[0]
    reponse = meteo.Meteo().repondre("meteo", ctx(faux_http(ReseauIndisponible("URLError"))))
    assert "Internet ne marche pas bien" in reponse.parties[0]
