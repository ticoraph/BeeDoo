import io
import urllib.error
from pathlib import Path

import pytest

pytest.importorskip("certifi")

from beedoo.config import Config  # noqa: E402
from beedoo.voice import tts  # noqa: E402


@pytest.fixture
def config(tmp_path: Path, monkeypatch) -> Config:
    monkeypatch.setenv("OPENAI_API_KEY", "cle-de-test-openai")
    return Config.load(env_file=tmp_path / "absent.env")


def test_vitesse_changes_the_voice_instruction():
    assert "débit lent" in tts.consigne(0.6)
    assert "débit rapide" in tts.consigne(1.4)
    assert "débit calme" in tts.consigne(1.0)


def test_missing_key_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(tts.TTSError):
        tts.synthesize(Config.load(env_file=tmp_path / "absent.env"), "Bonjour")


def test_request_content_and_pronunciation(config, monkeypatch):
    vu = {}

    class Reponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def faux_urlopen(request, timeout, context):
        vu["body"] = request.data.decode()
        vu["auth"] = request.get_header("Authorization")
        return Reponse(b"mp3")

    monkeypatch.setattr(tts.urllib.request, "urlopen", faux_urlopen)
    assert tts.synthesize(config, "Je suis BeeDoo") == b"mp3"
    assert "Bidou" in vu["body"] and "BeeDoo" not in vu["body"]
    assert vu["auth"] == "Bearer cle-de-test-openai"


def test_error_message_has_neither_text_nor_key(config, monkeypatch):
    def erreur(request, timeout, context):
        raise urllib.error.HTTPError("u", 429, "trop", {}, io.BytesIO(b'{"error":"texte secret Mamie"}'))

    monkeypatch.setattr(tts.urllib.request, "urlopen", erreur)
    with pytest.raises(tts.TTSError) as info:
        tts.synthesize(config, "texte secret Mamie")
    assert "429" in str(info.value)
    assert "Mamie" not in str(info.value) and "cle-de-test" not in str(info.value)


def test_network_failure_is_a_tts_error(config, monkeypatch):
    def coupe(request, timeout, context):
        raise urllib.error.URLError("pas de réseau")

    monkeypatch.setattr(tts.urllib.request, "urlopen", coupe)
    with pytest.raises(tts.TTSError):
        tts.synthesize(config, "Bonjour")


def test_chosen_voice_overrides_configured_one(config, monkeypatch):
    vu = {}

    class Reponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def faux_urlopen(request, timeout, context):
        vu["body"] = request.data.decode()
        return Reponse(b"mp3")

    monkeypatch.setattr(tts.urllib.request, "urlopen", faux_urlopen)
    tts.synthesize(config, "Salut")
    assert '"voice": "fable"' in vu["body"]
    tts.synthesize(config, "Salut", voix="coral")
    assert '"voice": "coral"' in vu["body"]
