from pathlib import Path

from beedoo.config import Config

ENV_NAMES = ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_STT_MODEL", "OPENAI_TTS_MODEL",
             "OPENAI_TTS_VOICE", "BEEDOO_DATA_DIR", "BEEDOO_WEB_PORT", "BEEDOO_DAEMON_URL",
             "BEEDOO_WEB_HOST", "BEEDOO_WEB_PASSWORD")


def test_defaults_without_env(tmp_path: Path, monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    config = Config.load(env_file=tmp_path / "absent.env")
    assert config.openai_model == "gpt-6-luna"
    assert config.stt_model == "gpt-4o-transcribe"
    assert config.tts_model == "gpt-4o-mini-tts"
    assert config.tts_voice == "fable"
    assert config.data_dir.name == "data"
    assert config.web_port == 8765
    assert config.web_host == "127.0.0.1" and config.web_password == ""
    assert config.daemon_url == "http://127.0.0.1:8000"
    assert config.missing_keys() == ["OPENAI_API_KEY"]


def test_key_never_in_repr(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "cle-de-test-openai")
    config = Config.load(env_file=tmp_path / "absent.env")
    assert "cle-de-test" not in repr(config)
    assert config.openai_api_key == "cle-de-test-openai"
    assert config.missing_keys() == []


def test_web_password_never_in_repr(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BEEDOO_WEB_PASSWORD", "mot-de-passe-de-test")
    monkeypatch.setenv("BEEDOO_WEB_HOST", " 0.0.0.0 ")
    config = Config.load(env_file=tmp_path / "absent.env")
    assert "mot-de-passe" not in repr(config)
    assert config.web_password == "mot-de-passe-de-test" and config.web_host == "0.0.0.0"
