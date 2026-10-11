from pathlib import Path

from beedoo.config import Config

ENV_NAMES = ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_STT_MODEL", "OPENAI_TTS_MODEL",
             "OPENAI_TTS_VOICE", "BEEDOO_DATA_DIR")


def test_defaults_without_env(tmp_path: Path, monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    config = Config.load(env_file=tmp_path / "absent.env")
    assert config.openai_model == "gpt-6-luna"
    assert config.stt_model == "gpt-4o-transcribe"
    assert config.tts_model == "gpt-4o-mini-tts"
    assert config.tts_voice == "fable"
    assert config.data_dir.name == "data"
    assert config.missing_keys() == ["OPENAI_API_KEY"]


def test_key_never_in_repr(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "cle-de-test-openai")
    config = Config.load(env_file=tmp_path / "absent.env")
    assert "cle-de-test" not in repr(config)
    assert config.openai_api_key == "cle-de-test-openai"
    assert config.missing_keys() == []
