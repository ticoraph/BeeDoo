from pathlib import Path

from beedoo.config import Config


def test_defaults_without_env(tmp_path: Path, monkeypatch):
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "BEEDOO_DATA_DIR"):
        monkeypatch.delenv(name, raising=False)
    config = Config.load(env_file=tmp_path / "absent.env")
    assert config.openai_model == "gpt-6-luna"
    assert config.data_dir.name == "data"
    assert config.missing_keys() == ["OPENAI_API_KEY", "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID"]


def test_keys_never_in_repr(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "cle-de-test-openai")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "cle-de-test-eleven")
    config = Config.load(env_file=tmp_path / "absent.env")
    assert "cle-de-test" not in repr(config)
    assert config.openai_api_key == "cle-de-test-openai"
