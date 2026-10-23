"""Conversation avec le LLM : prompt de BeeDoo rempli, historique court, réponse prête à être lue.

Le prompt vient de `prompts/beedoo_system.md`. L'historique reste en mémoire le temps d'une
conversation et n'est écrit nulle part (la mémoire durable est l'affaire de la phase 8).
Aucun contenu (question, réponse) dans les messages d'erreur ni les logs.
"""

import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime

import certifi

from beedoo.config import REPO_ROOT, Config

URL = "https://api.openai.com/v1/chat/completions"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
PROMPT = REPO_ROOT / "prompts" / "beedoo_system.md"

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre")

MAX_MESSAGES = 10  # historique gardé : les 5 derniers échanges
NE_SAIT_PAS = "Oh, je n'ai pas bien entendu. Tu peux répéter ?"


class LLMError(RuntimeError):
    """Le LLM n'a pas répondu (réseau, clé, quota). Le message ne contient jamais le texte échangé."""


def date_fr(maintenant: datetime) -> str:
    """« jeudi 23 octobre 2026, 15 heures 30 », sans dépendre de la langue du système."""
    return (f"{JOURS[maintenant.weekday()]} {maintenant.day} {MOIS[maintenant.month - 1]} "
            f"{maintenant.year}, {maintenant.hour} heures {maintenant.minute:02d}")


def system_prompt(prenom: str, souvenirs: str, maintenant: datetime, modele: str | None = None) -> str:
    """Le prompt sans son en-tête qui documente les variables, avec les variables remplies."""
    texte = (modele or PROMPT.read_text(encoding="utf-8")).split("\n---\n", 1)[-1]
    return (texte.replace("{{prenom}}", prenom).replace("{{souvenirs}}", souvenirs)
            .replace("{{date_heure}}", date_fr(maintenant)).strip())


def pour_etre_lu(texte: str) -> str:
    """Retire ce qu'une voix ne sait pas lire (mise en forme, émojis), au cas où le LLM en mettrait."""
    texte = re.sub(r"[*_#`>~]+", "", texte)
    texte = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", texte)
    return " ".join(texte.split())


class Chat:
    def __init__(self, config: Config, modele_prompt: str | None = None) -> None:
        self._config = config
        self._modele = modele_prompt  # pour les tests ; sinon lu dans prompts/
        self._historique: list[dict] = []

    def reset(self) -> None:
        self._historique = []

    def memoriser(self, texte: str, reponse: str) -> None:
        """Ajoute à l'historique un échange que le LLM n'a pas produit (mini-application)."""
        self._historique += [{"role": "user", "content": texte}, {"role": "assistant", "content": reponse}]
        self._historique = self._historique[-MAX_MESSAGES:]

    def reply(self, texte: str, prenom: str = "inconnu", souvenirs: str = "rien pour l'instant",
              maintenant: datetime | None = None) -> str:
        """Réponse de BeeDoo à ce que la personne vient de dire. Lève LLMError en cas d'échec."""
        if not self._config.openai_api_key:
            raise LLMError("clé OpenAI absente")
        systeme = system_prompt(prenom, souvenirs, maintenant or datetime.now(), self._modele)
        messages = [{"role": "system", "content": systeme}, *self._historique,
                    {"role": "user", "content": texte}]
        body = {"model": self._config.openai_model, "reasoning_effort": "low", "messages": messages}
        request = urllib.request.Request(
            URL, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self._config.openai_api_key}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60, context=SSL_CONTEXT) as response:
                reponse = pour_etre_lu(json.load(response)["choices"][0]["message"]["content"] or "")
        except urllib.error.HTTPError as error:
            raise LLMError(f"OpenAI a répondu {error.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError) as error:
            raise LLMError(f"réponse impossible ({type(error).__name__})") from None
        if not reponse:
            raise LLMError("réponse vide")
        self.memoriser(texte, reponse)
        return reponse
