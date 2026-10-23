from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from beedoo.config import Config
from beedoo.runtime import Runtime
from beedoo.settings import Settings
from beedoo.state import State
from beedoo.ui.web import create_app

PORT = 8765
LOCAL = {"Host": f"127.0.0.1:{PORT}"}


@pytest.fixture
def runtime(tmp_path: Path, monkeypatch) -> Runtime:
    monkeypatch.setenv("BEEDOO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "cle-de-test-openai")
    return Runtime(config=Config.load(env_file=tmp_path / "absent.env"), settings=Settings())


@pytest.fixture
def client(runtime: Runtime) -> TestClient:
    return TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")


def test_page_served_without_external_resources(client):
    page = client.get("/", headers=LOCAL)
    assert page.status_code == 200
    assert "BeeDoo" in page.text
    assert "http://" not in page.text and "https://" not in page.text


def test_status_has_no_secret(client):
    body = client.get("/api/status", headers=LOCAL)
    assert body.json() == {"etat": "veille", "muet": False, "volume": 0.7, "vitesse": 1.0}
    assert "cle-de-test" not in body.text


def test_muet_is_saved_and_forces_veille(client, runtime):
    runtime.machine.go(State.ECOUTE)
    response = client.post("/api/muet", json={"muet": True}, headers=LOCAL)
    assert response.json()["muet"] is True
    assert runtime.machine.state == State.VEILLE
    assert Settings.load(runtime.config.data_dir).muet is True


def test_foreign_host_refused(client):
    assert client.get("/api/status", headers={"Host": "exemple.org"}).status_code == 403


def test_foreign_origin_refused(client, runtime):
    reponse = client.post("/api/muet", json={"muet": True},
                          headers={**LOCAL, "Origin": "http://exemple.org"})
    assert reponse.status_code == 403
    assert runtime.settings.muet is False


def test_same_origin_accepted(client):
    reponse = client.post("/api/muet", json={"muet": False},
                          headers={**LOCAL, "Origin": f"http://127.0.0.1:{PORT}"})
    assert reponse.status_code == 200


def test_invalid_body_rejected(client):
    assert client.post("/api/muet", json={"muet": "peut-être"}, headers=LOCAL).status_code == 422


def test_server_start_stop_and_busy_port(runtime):
    import socket

    from beedoo.ui.web import WebServer

    with socket.socket() as libre:
        libre.bind(("127.0.0.1", 0))
        port = libre.getsockname()[1]
    premier = WebServer(runtime, port)
    premier.start()
    try:
        with pytest.raises(OSError):
            WebServer(runtime, port).start()
    finally:
        premier.stop()
    assert not premier._thread.is_alive()
