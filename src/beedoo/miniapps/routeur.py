"""Choisit la mini-application qui répond à une phrase, ou aucune (BeeDoo converse alors librement).

Règles (voir DECISIONS.md D5) :
- mot sûr -> la mini-application répond tout de suite ;
- mot vague -> BeeDoo demande d'abord « Tu veux que… ? » et attend un oui ou un non au tour suivant ;
- rien -> None, et la phrase part vers le LLM.
Les mini-applications désactivées dans l'interface sont ignorées.
"""

import logging
from collections.abc import Callable, Sequence

from beedoo.miniapps.base import Contexte, MiniApp, Reponse, contient, normaliser

log = logging.getLogger(__name__)

OUI = ("oui", "ouais", "ok", "d accord", "vas y", "va y", "bien sur", "volontiers", "avec plaisir",
       "pourquoi pas", "si tu veux", "s il te plait", "allez", "carrement", "j veux bien", "je veux bien")
NON = ("non", "non merci", "pas maintenant", "pas envie", "plus tard", "laisse tomber", "arrete")
REPONSE_NON = Reponse(("D'accord, pas de souci !",))


class Routeur:
    def __init__(self, apps: Sequence[MiniApp], desactivees: Callable[[], Sequence[str]] = lambda: ()) -> None:
        self._apps = list(apps)
        self._desactivees = desactivees
        self._en_attente: MiniApp | None = None  # mini-application proposée, réponse oui/non attendue

    def reset(self) -> None:
        self._en_attente = None

    def _actives(self) -> list[MiniApp]:
        coupees = set(self._desactivees())
        return [app for app in self._apps if app.nom not in coupees]

    def router(self, texte: str, contexte: Contexte) -> Reponse | None:
        propre = normaliser(texte)
        actives = self._actives()
        proposee, self._en_attente = self._en_attente, None  # une proposition ne vaut que pour un tour

        if proposee is not None and proposee in actives:
            if contient(propre, OUI) and not contient(propre, ("non",)):
                return self._lancer(proposee, propre, contexte)
            if contient(propre, NON):
                return REPONSE_NON

        for app in actives:
            if contient(propre, app.mots_surs):
                return self._lancer(app, propre, contexte)
        for app in actives:
            if app.mots_vagues and contient(propre, app.mots_vagues):
                self._en_attente = app
                return Reponse((app.proposition,))
        return None

    def _lancer(self, app: MiniApp, propre: str, contexte: Contexte) -> Reponse | None:
        log.info("mini-application : %s", app.nom)
        try:
            return app.repondre(propre, contexte)
        except Exception as erreur:  # une mini-application cassée ne doit pas couper la conversation
            log.warning("mini-application %s en erreur (%s)", app.nom, type(erreur).__name__)
            return None
