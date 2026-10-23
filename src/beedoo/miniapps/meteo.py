"""Météo : « Dehors, il fait 14 degrés. Le ciel est couvert… », aujourd'hui ou demain.

Source : Open-Meteo (https://open-meteo.com), gratuit, sans clé. Le nom de la ville (réglage `ville`,
dans `data/settings.json`) et ses coordonnées sont envoyés à ce service, voir DECISIONS.md.
La phrase est construite par le code (pas par le LLM) : pas d'invention, pas de coût, testable.
"""

import logging
import urllib.parse

from beedoo.miniapps.base import Contexte, MiniApp, Reponse
from beedoo.miniapps.http import ReseauIndisponible

log = logging.getLogger(__name__)

GEOCODAGE = "https://geocoding-api.open-meteo.com/v1/search"
PREVISIONS = "https://api.open-meteo.com/v1/forecast"

# Codes météo de l'OMM utilisés par Open-Meteo -> ce que dit BeeDoo.
CIEL = {
    0: "Le ciel est tout bleu.",
    1: "Il y a presque pas de nuages.",
    2: "Il y a quelques nuages.",
    3: "Le ciel est couvert.",
    45: "Il y a du brouillard.", 48: "Il y a du brouillard.",
    51: "Il y a un peu de bruine.", 53: "Il y a de la bruine.", 55: "Il y a beaucoup de bruine.",
    56: "Il y a de la bruine qui gèle.", 57: "Il y a de la bruine qui gèle.",
    61: "Il pleut un petit peu.", 63: "Il pleut.", 65: "Il pleut beaucoup.",
    66: "Il pleut et ça gèle.", 67: "Il pleut et ça gèle.",
    71: "Il neige un peu.", 73: "Il neige.", 75: "Il neige beaucoup.", 77: "Il tombe des petits flocons.",
    80: "Il y a des averses.", 81: "Il y a des averses.", 82: "Il y a de grosses averses.",
    85: "Il y a des averses de neige.", 86: "Il y a des averses de neige.",
    95: "Il y a de l'orage.", 96: "Il y a de l'orage.", 99: "Il y a de l'orage.",
}
PLUIE = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
NEIGE = {71, 73, 75, 77, 85, 86}
ORAGE = {95, 96, 99}


def nombre(valeur: float) -> str:
    n = round(valeur)
    return f"moins {abs(n)}" if n < 0 else str(n)


def degres(valeur: float) -> str:
    return f"{nombre(valeur)} {'degré' if abs(round(valeur)) <= 1 else 'degrés'}"


def entre(mini: float, maxi: float) -> str:
    return f"entre {nombre(mini)} et {degres(maxi)}"


def conseil(code: int, maximum: float, proba_pluie: float | None) -> str:
    if code in ORAGE:
        return "Reste bien au chaud à la maison."
    if code in PLUIE or (proba_pluie is not None and proba_pluie >= 60):
        return "Prends ton parapluie !"
    if code in NEIGE or maximum <= 3:
        return "Mets ton gros manteau !"
    if maximum >= 28:
        return "Il fait chaud, pense à boire de l'eau !"
    return ""


def phrase(previsions: dict, demain: bool) -> str:
    """Texte dit par BeeDoo à partir de la réponse d'Open-Meteo (`current` et `daily`)."""
    jour = previsions["daily"]
    i = 1 if demain else 0
    code = int(jour["weather_code"][i])
    mini, maxi = jour["temperature_2m_min"][i], jour["temperature_2m_max"][i]
    proba = (jour.get("precipitation_probability_max") or [None, None])[i]
    ciel = CIEL.get(code, "Le temps est un peu spécial.")
    if demain:
        morceaux = [f"Demain, il fera {entre(mini, maxi)}.", ciel]
    else:
        actuel = previsions["current"]
        code_actuel = int(actuel["weather_code"])
        morceaux = [f"Dehors, il fait {degres(actuel['temperature_2m'])}.", CIEL.get(code_actuel, ciel),
                    f"Aujourd'hui, il fera {entre(mini, maxi)}."]
        code = code if code in PLUIE | NEIGE | ORAGE else code_actuel  # un conseil pour la journée entière
    morceaux.append(conseil(code, maxi, proba))
    return " ".join(m for m in morceaux if m)


class Meteo(MiniApp):
    nom = "meteo"
    titre = "Météo"
    mots_surs = ("meteo", "quel temps", "quelle temperature", "temperature", "pleuvoir", "il pleut", "va t il pleuvoir",
                 "il fait beau", "il fait chaud", "il fait froid", "il va neiger", "faut il un parapluie")
    mots_vagues = ("dehors", "parapluie", "manteau")
    proposition = "Tu veux que je regarde la météo ?"

    def repondre(self, texte: str, contexte: Contexte) -> Reponse:
        ville = contexte.settings.ville
        if not ville:
            return Reponse(("Je ne sais pas où tu habites. Tu peux écrire le nom de ta ville dans mes réglages.",))
        try:
            lieu = self._lieu(ville, contexte)
            if lieu is None:
                return Reponse(("Je ne trouve pas ta ville. Tu peux vérifier son nom dans mes réglages ?",))
            url = PREVISIONS + "?" + urllib.parse.urlencode({
                "latitude": lieu[0], "longitude": lieu[1], "timezone": "auto", "forecast_days": 2,
                "current": "temperature_2m,weather_code",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"})
            texte_meteo = phrase(contexte.http_json(url), demain="demain" in texte.split())
        except (ReseauIndisponible, KeyError, IndexError, TypeError, ValueError) as erreur:
            log.warning("météo indisponible (%s)", type(erreur).__name__)
            return Reponse(("Je n'arrive pas à regarder le ciel. Internet ne marche pas bien.",))
        return Reponse((texte_meteo,))

    @staticmethod
    def _lieu(ville: str, contexte: Contexte) -> tuple[float, float] | None:
        url = GEOCODAGE + "?" + urllib.parse.urlencode({"name": ville, "count": 1, "language": "fr", "format": "json"})
        trouves = contexte.http_json(url).get("results") or []
        return (trouves[0]["latitude"], trouves[0]["longitude"]) if trouves else None
