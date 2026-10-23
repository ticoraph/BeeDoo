import io
import urllib.error
import wave
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("certifi")

from beedoo.config import Config  # noqa: E402
from beedoo.voice import stt  # noqa: E402


@pytest.fixture
def config(tmp_path: Path, monkeypatch) -> Config:
    monkeypatch.setenv("OPENAI_API_KEY", "cle-de-test-openai")
    return Config.load(env_file=tmp_path / "absent.env")


def test_to_wav_is_valid_mono_16_bits():
    wav = stt.to_wav(np.array([0.0, 0.5, -0.5, 2.0]), 16000)  # 2.0 est ramené à 1.0
    with wave.open(io.BytesIO(wav)) as f:
        assert (f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()) == (1, 2, 16000, 4)
        assert np.frombuffer(f.readframes(4), dtype=np.int16).tolist() == [0, 16383, -16383, 32767]


@pytest.mark.parametrize("texte", ["Bonjour BeeDoo, ça va ?", "Oui", "J'ai fait un gâteau à la fraise.",
                                   "Ok Google", "Où est ma lunette ?"])
def test_real_sentences_are_plausible(texte):
    assert stt.plausible(texte)


@pytest.mark.parametrize("texte", ["", "  ", "?", "嘶嘶嘶", "あー。", "Sous-titrage Société Radio-Canada",
                                   "Sous-titres réalisés par la communauté d'Amara.org",
                                   "Merci d'avoir regardé cette vidéo !", "a"])
def test_invented_or_empty_text_is_rejected(texte):
    assert not stt.plausible(texte)


def test_transcribe_normalizes_name_and_sends_key(config, monkeypatch):
    vu = {}

    class Reponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def faux_urlopen(request, timeout, context):
        vu["auth"] = request.get_header("Authorization")
        vu["corps"] = request.data
        return Reponse(b'{"text": " Salut Bidou, ca va ?"}')

    monkeypatch.setattr(stt.urllib.request, "urlopen", faux_urlopen)
    assert stt.transcribe(config, np.zeros(1600), 16000) == "Salut BeeDoo, ca va ?"
    assert vu["auth"] == "Bearer cle-de-test-openai"
    assert b'name="language"' in vu["corps"] and b"fr" in vu["corps"] and b"RIFF" in vu["corps"]


def test_errors_carry_neither_text_nor_key(config, monkeypatch):
    def erreur(request, timeout, context):
        raise urllib.error.HTTPError("u", 401, "non", {}, io.BytesIO(b'{"error":"cle-de-test-openai"}'))

    monkeypatch.setattr(stt.urllib.request, "urlopen", erreur)
    with pytest.raises(stt.STTError) as info:
        stt.transcribe(config, np.zeros(1600), 16000)
    assert "401" in str(info.value) and "cle-de-test" not in str(info.value)


def test_missing_key_and_network_error(tmp_path, monkeypatch, config):
    monkeypatch.setattr(stt.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("coupé")))
    with pytest.raises(stt.STTError):
        stt.transcribe(config, np.zeros(1600), 16000)
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(stt.STTError):
        stt.transcribe(Config.load(env_file=tmp_path / "absent.env"), np.zeros(1600), 16000)
