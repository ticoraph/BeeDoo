import json
from pathlib import Path

from beedoo.settings import SETTINGS_FILE, Settings


def test_defaults_when_file_absent(tmp_path: Path):
    assert Settings.load(tmp_path) == Settings()


def test_save_then_load(tmp_path: Path):
    Settings(muet=True, vitesse=1.2, voix="coral").save(tmp_path)
    assert Settings.load(tmp_path) == Settings(muet=True, vitesse=1.2, voix="coral")
    assert not list(tmp_path.glob("*.tmp"))


def test_out_of_range_values_are_clamped(tmp_path: Path):
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"volume": 7, "vitesse": 0, "voix": "inconnue"}))
    settings = Settings.load(tmp_path)
    assert settings.vitesse == 0.5
    assert settings.voix == ""  # une voix hors liste est ignorée ; l'ancien « volume » aussi


def test_corrupt_or_wrong_type_file_gives_defaults(tmp_path: Path):
    (tmp_path / SETTINGS_FILE).write_text("{pas du json")
    assert Settings.load(tmp_path) == Settings()
    (tmp_path / SETTINGS_FILE).write_text("[1, 2]")
    assert Settings.load(tmp_path) == Settings()
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"vitesse": "vite"}))
    assert Settings.load(tmp_path) == Settings()


def test_unknown_keys_are_ignored(tmp_path: Path):
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"muet": True, "inconnu": 1}))
    assert Settings.load(tmp_path) == Settings(muet=True)


def test_city_and_disabled_miniapps_are_saved_and_cleaned(tmp_path):
    Settings(ville="  Saint   Étienne ", miniapps_desactivees=["meteo", "toto", "meteo"]).save(tmp_path)
    relu = Settings.load(tmp_path)
    assert relu.ville == "Saint Étienne" and relu.miniapps_desactivees == ["meteo", "toto"]
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"miniapps_desactivees": "toto", "ville": "x" * 200}))
    relu = Settings.load(tmp_path)
    assert relu.miniapps_desactivees == [] and len(relu.ville) == 80
