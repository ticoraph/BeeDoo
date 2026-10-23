import json
from pathlib import Path

from beedoo.settings import SETTINGS_FILE, Settings


def test_defaults_when_file_absent(tmp_path: Path):
    assert Settings.load(tmp_path) == Settings()


def test_save_then_load(tmp_path: Path):
    Settings(muet=True, volume=0.3, vitesse=1.2).save(tmp_path)
    assert Settings.load(tmp_path) == Settings(muet=True, volume=0.3, vitesse=1.2)
    assert not list(tmp_path.glob("*.tmp"))


def test_out_of_range_values_are_clamped(tmp_path: Path):
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"volume": 7, "vitesse": 0}))
    settings = Settings.load(tmp_path)
    assert settings.volume == 1.0
    assert settings.vitesse == 0.5


def test_corrupt_or_wrong_type_file_gives_defaults(tmp_path: Path):
    (tmp_path / SETTINGS_FILE).write_text("{pas du json")
    assert Settings.load(tmp_path) == Settings()
    (tmp_path / SETTINGS_FILE).write_text("[1, 2]")
    assert Settings.load(tmp_path) == Settings()
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"volume": "fort"}))
    assert Settings.load(tmp_path) == Settings()


def test_unknown_keys_are_ignored(tmp_path: Path):
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"muet": True, "inconnu": 1}))
    assert Settings.load(tmp_path) == Settings(muet=True)
