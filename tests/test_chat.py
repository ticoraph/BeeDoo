import io
import json
import urllib.error
from datetime import datetime
from pathlib import Path

import pytest

pytest.importorskip("certifi")

from beedoo.config import Config  # noqa: E402
from beedoo.llm import chat  # noqa: E402

MODELE = "En-tête\n\n---\n\nTu es BeeDoo. Personne : {{prenom}}. Souvenirs : {{souvenirs}}. Date : {{date_heure}}."
JEUDI = datetime(2026, 10, 22, 15, 5)


@pytest.fixture
def config(tmp_path: Path, monkeypatch) -> Config:
    monkeypatch.setenv("OPENAI_API_KEY", "cle-de-test-openai")
    return Config.load(env_file=tmp_path / "absent.env")


class Reponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def serveur(monkeypatch, *textes):
    """Remplace OpenAI : renvoie les textes un par un et note les requêtes."""
    requetes = []
    suite = iter(textes)

    def faux(request, timeout, context):
        requetes.append(json.loads(request.data))
        return Reponse(json.dumps({"choices": [{"message": {"content": next(suite)}}]}).encode())

    monkeypatch.setattr(chat.urllib.request, "urlopen", faux)
    return requetes


def test_french_date_does_not_depend_on_system_language():
    assert chat.date_fr(JEUDI) == "jeudi 22 octobre 2026, 15 heures 05"
    assert chat.date_fr(datetime(2026, 2, 1, 0, 0)) == "dimanche 1 février 2026, 0 heures 00"


def test_system_prompt_fills_variables_and_drops_header():
    texte = chat.system_prompt("Léa", "aime les chats", JEUDI, MODELE)
    assert texte == "Tu es BeeDoo. Personne : Léa. Souvenirs : aime les chats. Date : jeudi 22 octobre 2026, 15 heures 05."
    assert "En-tête" not in texte and "{{" not in texte


def test_real_prompt_has_all_variables_filled():
    texte = chat.system_prompt("Léa", "rien", JEUDI)
    assert "{{" not in texte and "Léa" in texte and "tu es beedoo" in texte.lower()


def test_reply_cleans_formatting_and_keeps_history(config, monkeypatch):
    requetes = serveur(monkeypatch, "**Bonjour** Léa 😀 ! ", "Oh, chouette !")
    discussion = chat.Chat(config, MODELE)
    assert discussion.reply("Salut", "Léa", maintenant=JEUDI) == "Bonjour Léa !"
    assert discussion.reply("J'ai un chat", "Léa", maintenant=JEUDI) == "Oh, chouette !"
    roles = [m["role"] for m in requetes[1]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert requetes[1]["messages"][2]["content"] == "Bonjour Léa !"  # l'historique garde le texte nettoyé
    assert requetes[0]["model"] == config.openai_model


def test_history_is_bounded_and_reset(config, monkeypatch):
    serveur(monkeypatch, *["ok"] * 20)
    discussion = chat.Chat(config, MODELE)
    for i in range(12):
        discussion.reply(f"phrase {i}", maintenant=JEUDI)
    assert len(discussion._historique) == chat.MAX_MESSAGES
    discussion.reset()
    assert discussion._historique == []


def test_failure_does_not_pollute_history_nor_leak(config, monkeypatch):
    def erreur(request, timeout, context):
        raise urllib.error.HTTPError("u", 429, "trop", {}, io.BytesIO(b"texte confidentiel"))

    monkeypatch.setattr(chat.urllib.request, "urlopen", erreur)
    discussion = chat.Chat(config, MODELE)
    with pytest.raises(chat.LLMError) as info:
        discussion.reply("secret de Mamie", maintenant=JEUDI)
    assert "429" in str(info.value) and "Mamie" not in str(info.value)
    assert discussion._historique == []


def test_empty_answer_and_missing_key(config, monkeypatch, tmp_path):
    serveur(monkeypatch, "  ")
    with pytest.raises(chat.LLMError):
        chat.Chat(config, MODELE).reply("Salut", maintenant=JEUDI)
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(chat.LLMError):
        chat.Chat(Config.load(env_file=tmp_path / "absent.env"), MODELE).reply("Salut")
