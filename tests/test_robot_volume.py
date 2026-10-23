import io
import json
import urllib.error

import pytest

from beedoo import robot_volume


class Reponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_read_and_set(monkeypatch):
    vus = []

    def faux(requete, timeout):
        vus.append((requete.full_url, requete.data))
        return Reponse(json.dumps({"volume": 55, "platform": "Darwin"}).encode())

    monkeypatch.setattr(robot_volume.urllib.request, "urlopen", faux)
    assert robot_volume.lire("http://d:8000") == 55
    assert robot_volume.regler("http://d:8000", 30)
    assert vus[0] == ("http://d:8000/api/volume/current", None)
    assert vus[1][0] == "http://d:8000/api/volume/set" and json.loads(vus[1][1]) == {"volume": 30}


def test_daemon_down_is_not_an_exception(monkeypatch):
    def coupe(requete, timeout):
        raise urllib.error.URLError("refusé")

    monkeypatch.setattr(robot_volume.urllib.request, "urlopen", coupe)
    assert robot_volume.lire("http://d:8000") is None
    assert robot_volume.regler("http://d:8000", 30) is False


def test_out_of_range_refused():
    with pytest.raises(ValueError):
        robot_volume.regler("http://d:8000", 101)
