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
    assert body.json() == {"etat": "veille", "muet": False, "vitesse": 1.0}
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


def test_gestes_listed_and_unavailable_without_robot(client):
    liste = client.get("/api/gestes", headers=LOCAL).json()
    assert "oui" in liste["gestes"] and liste["disponible"] is False
    assert client.post("/api/geste", json={"nom": "oui"}, headers=LOCAL).status_code == 503
    assert client.post("/api/geste", json={"nom": "danse"}, headers=LOCAL).status_code == 404


def test_geste_played_and_busy(runtime):
    from beedoo.gestures.player import GesturePlayer

    class Lent:
        def __init__(self):
            self.n = 0

        def goto_target(self, **kwargs):
            self.n += 1
            import time
            time.sleep(0.2)

    robot = Lent()
    runtime.gestes = GesturePlayer(robot)
    client = TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")
    assert client.post("/api/geste", json={"nom": "non"}, headers=LOCAL).status_code == 200
    assert client.post("/api/geste", json={"nom": "oui"}, headers=LOCAL).status_code == 409
    assert client.get("/api/gestes", headers=LOCAL).json()["occupe"] is True
    runtime.gestes.stop()
    assert robot.n >= 1


class FauxEnrolement:
    def __init__(self):
        self.demandes = []
        self.occupe = False

    @property
    def en_cours(self):
        return self.occupe

    def status(self):
        return {"etat": "libre", "ajoutes": 0, "total": 6, "essais": 0, "derniere": None, "taille": None,
                "min_taille": 60}

    def start(self, nom):
        if self.occupe:
            return False
        self.demandes.append(nom)
        return True


@pytest.fixture
def monde_visages(runtime):
    from beedoo.vision.faces import FaceStore
    from beedoo.vision.greeter import Greeter

    runtime.faces = FaceStore(runtime.config.data_dir)
    runtime.faces.add("Léa", [[1.0, 0.0]])
    runtime.greeter = Greeter()
    runtime.enrolement = FauxEnrolement()
    return runtime, TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")


def test_people_listed_without_embeddings_content(monde_visages):
    _, client = monde_visages
    corps = client.get("/api/personnes", headers=LOCAL)
    assert corps.json()["personnes"] == [{"id": "lea", "nom": "Léa", "empreintes": 1}]
    assert "1.0" not in corps.text  # les empreintes elles-mêmes ne sortent jamais


def test_add_person_starts_enrollment_and_cleans_name(monde_visages):
    runtime, client = monde_visages
    reponse = client.post("/api/personnes", json={"prenom": "  Mamie   Jeanne "}, headers=LOCAL)
    assert reponse.status_code == 202
    assert runtime.enrolement.demandes == ["Mamie Jeanne"]


@pytest.mark.parametrize("prenom", ["", "   ", "///", "x" * 41])
def test_invalid_names_rejected(monde_visages, prenom):
    runtime, client = monde_visages
    assert client.post("/api/personnes", json={"prenom": prenom}, headers=LOCAL).status_code == 422
    assert runtime.enrolement.demandes == []


def test_enrollment_busy_and_no_camera(monde_visages):
    runtime, client = monde_visages
    runtime.enrolement.occupe = True
    assert client.post("/api/personnes", json={"prenom": "Paul"}, headers=LOCAL).status_code == 409
    runtime.enrolement = None
    assert client.post("/api/personnes", json={"prenom": "Paul"}, headers=LOCAL).status_code == 503


def test_rename_and_duplicate(monde_visages):
    runtime, client = monde_visages
    runtime.faces.add("Paul", [[0.0, 1.0]])
    assert client.patch("/api/personnes/lea", json={"prenom": "Léane"}, headers=LOCAL).status_code == 200
    assert runtime.faces.people() == ["leane", "paul"]
    assert client.patch("/api/personnes/leane", json={"prenom": "Paul"}, headers=LOCAL).status_code == 409
    assert client.patch("/api/personnes/absent", json={"prenom": "Zoé"}, headers=LOCAL).status_code == 404


def test_delete_person_forgets_everything(monde_visages):
    runtime, client = monde_visages
    assert client.delete("/api/personnes/lea", headers=LOCAL).status_code == 200
    assert runtime.faces.people() == []
    assert not (runtime.config.data_dir / "personnes" / "lea").exists()
    assert client.delete("/api/personnes/lea", headers=LOCAL).status_code == 404


def test_path_tricks_do_not_reach_the_disk(monde_visages):
    runtime, client = monde_visages
    for pid in ("..", "%2e%2e%2f", "..%2Flea", "%2Fetc%2Fpasswd"):
        assert client.delete(f"/api/personnes/{pid}", headers=LOCAL).status_code in (404, 405)
    assert runtime.faces.people() == ["lea"]


def test_foreign_origin_cannot_delete(monde_visages):
    runtime, client = monde_visages
    reponse = client.delete("/api/personnes/lea", headers={**LOCAL, "Origin": "http://exemple.org"})
    assert reponse.status_code == 403 and runtime.faces.people() == ["lea"]


def test_vision_endpoint_without_and_with_loop(monde_visages):
    runtime, client = monde_visages
    assert client.get("/api/vision", headers=LOCAL).json()["statut"] == "indisponible"

    class FausseVision:
        def status(self):
            return {"statut": "reconnu", "taille": 74, "personne": "lea", "age": 0.4}

    runtime.vision = FausseVision()
    corps = client.get("/api/vision", headers=LOCAL).json()
    assert corps["statut"] == "reconnu" and corps["nom"] == "Léa" and "personne" not in corps
    assert corps["min_taille"] >= 1


def test_reglages_voice_and_speed_saved(runtime, monkeypatch):
    from beedoo import robot_volume

    monkeypatch.setattr(robot_volume, "lire", lambda url: 93)
    client = TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")
    lecture = client.get("/api/reglages", headers=LOCAL).json()
    assert lecture["voix"] == "fable" and lecture["volume"] == 93 and "coral" in lecture["voix_possibles"]
    reponse = client.post("/api/reglages", json={"voix": "coral", "vitesse": 1.3}, headers=LOCAL)
    assert reponse.status_code == 200 and reponse.json()["voix"] == "coral"
    sauve = Settings.load(runtime.config.data_dir)
    assert sauve.voix == "coral" and sauve.vitesse == 1.3


@pytest.mark.parametrize("corps", [{"voix": "inconnue"}, {"vitesse": 9}, {"volume": 150}, {"volume": -1}])
def test_invalid_reglages_rejected(runtime, monkeypatch, corps):
    from beedoo import robot_volume

    appels = []
    monkeypatch.setattr(robot_volume, "regler", lambda url, v: appels.append(v) or True)
    client = TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")
    assert client.post("/api/reglages", json=corps, headers=LOCAL).status_code == 422
    assert appels == [] and runtime.settings.voix == ""


def test_volume_goes_to_the_daemon_and_failure_is_reported(runtime, monkeypatch):
    from beedoo import robot_volume

    vus = []
    monkeypatch.setattr(robot_volume, "regler", lambda url, v: vus.append((url, v)) or True)
    monkeypatch.setattr(robot_volume, "lire", lambda url: 40)
    client = TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")
    assert client.post("/api/reglages", json={"volume": 40}, headers=LOCAL).status_code == 200
    assert vus == [("http://127.0.0.1:8000", 40)]
    monkeypatch.setattr(robot_volume, "regler", lambda url, v: False)
    assert client.post("/api/reglages", json={"volume": 50}, headers=LOCAL).status_code == 502


def test_voice_test_needs_speaker_and_no_mute(runtime):
    client = TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")
    assert client.post("/api/test-voix", headers=LOCAL).status_code == 503

    class Voix:
        dit = []

        def say(self, texte):
            self.dit.append(texte)

    runtime.speaker = Voix()
    assert client.post("/api/test-voix", headers=LOCAL).status_code == 202
    runtime.settings.muet = True
    assert client.post("/api/test-voix", headers=LOCAL).status_code == 409


def test_echange_endpoint(runtime):
    client = TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")
    assert client.get("/api/echange", headers=LOCAL).json() == {"echange": None}
    runtime.echange = {"entendu": "Salut", "dit": "Coucou"}
    assert client.get("/api/echange", headers=LOCAL).json()["echange"]["dit"] == "Coucou"


def test_tracking_switch_is_saved_and_applied(runtime, monkeypatch):
    from beedoo import robot_volume

    monkeypatch.setattr(robot_volume, "lire", lambda url: 50)

    class Suivi:
        voulu = []

        def set_voulu(self, v):
            self.voulu.append(v)

    runtime.suivi = Suivi()
    client = TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")
    assert client.get("/api/reglages", headers=LOCAL).json()["suivi"] is True
    assert client.post("/api/reglages", json={"suivi": False}, headers=LOCAL).json()["suivi"] is False
    assert Suivi.voulu == [False] and Settings.load(runtime.config.data_dir).suivi is False


def test_city_saved_from_the_page(runtime, monkeypatch):
    from beedoo import robot_volume

    monkeypatch.setattr(robot_volume, "lire", lambda url: 50)
    client = TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")
    assert client.post("/api/reglages", json={"ville": "Lyon"}, headers=LOCAL).json()["ville"] == "Lyon"
    assert Settings.load(runtime.config.data_dir).ville == "Lyon"
    assert client.post("/api/reglages", json={"ville": "x" * 81}, headers=LOCAL).status_code == 422


def test_miniapps_listed_and_toggled(runtime):
    from beedoo.miniapps import toutes

    runtime.miniapps = toutes()
    client = TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")
    liste = client.get("/api/miniapps", headers=LOCAL).json()["miniapps"]
    assert [m["nom"] for m in liste] == ["toto", "meteo"] and all(m["active"] for m in liste)
    reponse = client.post("/api/miniapps/toto", json={"active": False}, headers=LOCAL)
    assert [m["active"] for m in reponse.json()["miniapps"]] == [False, True]
    assert Settings.load(runtime.config.data_dir).miniapps_desactivees == ["toto"]
    assert client.post("/api/miniapps/toto", json={"active": True}, headers=LOCAL).status_code == 200
    assert Settings.load(runtime.config.data_dir).miniapps_desactivees == []
    assert client.post("/api/miniapps/inconnue", json={"active": True}, headers=LOCAL).status_code == 404
