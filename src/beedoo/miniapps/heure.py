"""Heure et date, dites comme une personne : « Il est trois heures et demie de l'après-midi. »

Aucun réseau : l'heure est celle de la machine. Les mots-clés sont volontairement précis
(« quelle heure », pas « heure » : « je suis à l'heure » ne doit rien déclencher).
"""

from datetime import datetime

from beedoo.llm.chat import JOURS, MOIS
from beedoo.miniapps.base import Contexte, MiniApp, Reponse, contient

PETITS = {1: "une", 2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six", 7: "sept", 8: "huit", 9: "neuf",
          10: "dix", 11: "onze", 12: "douze", 13: "treize", 14: "quatorze", 15: "quinze", 16: "seize",
          17: "dix-sept", 18: "dix-huit", 19: "dix-neuf", 20: "vingt"}


def heure_parlee(t: datetime) -> str:
    """« 15:30 » -> « 3 heures et demie de l'après-midi » ; midi et minuit à part ; « moins » à partir de 40."""
    minute = t.minute
    heure = (t.hour + 1) % 24 if minute >= 40 else t.hour  # à partir de 40, on dit l'heure suivante « moins… »
    if heure == 0:
        base, periode, masculin = "minuit", "", True
    elif heure == 12:
        base, periode, masculin = "midi", "", True
    else:
        h12 = heure % 12
        base = "une heure" if h12 == 1 else f"{h12} heures"
        periode = (" du matin" if heure < 12 else " de l'après-midi" if heure < 18 else " du soir")
        masculin = False

    if minute == 0:
        suite = ""
    elif minute == 15:
        suite = " et quart"
    elif minute == 30:
        suite = " et demi" if masculin else " et demie"
    elif minute == 45:
        suite = " moins le quart"
    elif minute >= 40:
        suite = f" moins {PETITS[60 - minute]}"  # 40 -> « moins vingt » ... 59 -> « moins une »
    else:
        suite = f" {PETITS[minute]}" if minute < 10 else f" {minute}"
    return f"{base}{suite}{periode}"


def date_parlee(t: datetime) -> str:
    jour = "premier" if t.day == 1 else str(t.day)
    return f"{JOURS[t.weekday()]} {jour} {MOIS[t.month - 1]} {t.year}"


class HeureDate(MiniApp):
    nom = "heure"
    titre = "Heure et date"
    mots_surs = ("quelle heure", "quel heure", "heure est il", "tu as l heure", "t as l heure", "tu peux me dire l heure",
                 "quel jour", "quelle date", "on est le combien", "quel mois", "quelle annee", "en quelle annee")
    proposition = "Tu veux que je te dise l'heure ?"

    def repondre(self, texte: str, contexte: Contexte) -> Reponse:
        maintenant = contexte.maintenant()
        veut_heure = contient(texte, ("quelle heure", "quel heure", "heure est il", "tu as l heure", "t as l heure",
                                      "tu peux me dire l heure"))
        veut_mois = contient(texte, ("quel mois",)) and not contient(texte, ("quel jour", "quelle date", "combien"))
        veut_annee = contient(texte, ("quelle annee", "en quelle annee")) and not veut_mois
        if veut_mois:
            parties = [f"Nous sommes en {MOIS[maintenant.month - 1]}."]
        elif veut_annee:
            parties = [f"Nous sommes en {maintenant.year}."]
        elif contient(texte, ("quel jour", "quelle date", "on est le combien")) or not veut_heure:
            parties = [f"Nous sommes le {date_parlee(maintenant)}."]
        else:
            parties = []
        if veut_heure:
            parties.append(f"Il est {heure_parlee(maintenant)}.")
        return Reponse((" ".join(parties),))
