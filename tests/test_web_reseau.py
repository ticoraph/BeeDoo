"""Accès à l'interface depuis le réseau local : fermé par défaut, mot de passe obligatoire, essais limités."""

import base64
import logging
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from beedoo.config import Config  # noqa: E402
from beedoo.runtime import Runtime  # noqa: E402
from beedoo.settings import Settings  # noqa: E402
from beedoo.ui.web import LimiteEssais, acces_web, create_app, mot_de_passe_correct  # noqa: E402

PORT = 8765
MDP = "un-bon-mot-de-passe"
LAN = {"Host": f"192.168.1.20:{PORT}"}


def basic(mdp: str, identifiant: str = "beedoo") -> dict:
    jeton = base64.b64encode(f"{identifiant}:{mdp}".encode()).decode()
    return {"Authorization": f"Basic {jeton}"}


@pytest.fixture
def runtime(tmp_path: Path, monkeypatch) -> Runtime:
    monkeypatch.setenv("BEEDOO_DATA_DIR", str(tmp_path))
    return Runtime(config=Config.load(env_file=tmp_path / "absent.env"), settings=Settings())


def client(runtime, mot_de_passe=MDP, limite=None) -> TestClient:
    return TestClient(create_app(runtime, PORT, mot_de_passe, limite), base_url=f"http://192.168.1.20:{PORT}")


# --- décision d'ouvrir ou non ---
@pytest.mark.parametrize("hote", ["", "127.0.0.1", "localhost", "::1", " 127.0.0.1 "])
def test_local_addresses_stay_local_without_any_password(hote):
    assert acces_web(hote, "") == ("127.0.0.1", None)
    assert acces_web(hote, MDP) == ("127.0.0.1", None)  # un mot de passe inutile n'ouvre rien


@pytest.mark.parametrize("mdp", ["", "court", "1234567"])
def test_network_address_without_a_good_password_is_refused(mdp, caplog):
    with caplog.at_level(logging.ERROR):
        assert acces_web("0.0.0.0", mdp) == ("127.0.0.1", None)
    assert "BEEDOO_WEB_PASSWORD" in caplog.text


def test_network_address_with_a_good_password_is_opened(caplog):
    with caplog.at_level(logging.WARNING):
        assert acces_web("0.0.0.0", MDP) == ("0.0.0.0", MDP)
    assert MDP not in caplog.text  # le mot de passe n'est jamais écrit dans les logs


# --- authentification ---
def test_everything_needs_the_password_including_the_page(runtime):
    c = client(runtime)
    for chemin in ("/", "/api/status", "/api/personnes", "/api/echange", "/api/journal", "/api/reglages"):
        reponse = c.get(chemin, headers=LAN)
        assert reponse.status_code == 401, chemin
        assert "Basic" in reponse.headers["www-authenticate"]


def test_writes_need_the_password_too(runtime):
    c = client(runtime)
    assert c.post("/api/muet", json={"muet": True}, headers=LAN).status_code == 401
    assert runtime.settings.muet is False
    assert c.delete("/api/personnes/lea", headers=LAN).status_code == 401


def test_right_password_gives_access_whatever_the_username(runtime):
    c = client(runtime)
    assert c.get("/api/status", headers={**LAN, **basic(MDP)}).json()["reseau"] is True
    assert c.get("/", headers={**LAN, **basic(MDP, "n-importe-qui")}).status_code == 200
    assert c.post("/api/muet", json={"muet": True}, headers={**LAN, **basic(MDP)}).status_code == 200
    assert runtime.settings.muet is True


@pytest.mark.parametrize("en_tete", [None, "", "Basic", "Basic !!!pas-du-base64", "Bearer abc", "Basic " + "A" * 3,
                                     basic("mauvais")["Authorization"], basic("")["Authorization"],
                                     basic(MDP + "x")["Authorization"], basic(MDP[:-1])["Authorization"]])
def test_wrong_or_malformed_credentials_are_refused(runtime, en_tete):
    headers = dict(LAN)
    if en_tete is not None:
        headers["Authorization"] = en_tete
    assert client(runtime).get("/api/status", headers=headers).status_code == 401


def test_accented_password_and_colon_in_password(runtime):
    for mdp in ("mot-de-passe-éàù-1234", "a:b:c:d:e:f:g:h"):
        assert client(runtime, mdp).get("/api/status", headers={**LAN, **basic(mdp)}).status_code == 200


def test_password_comparison_function():
    assert mot_de_passe_correct(basic(MDP)["Authorization"], MDP)
    assert mot_de_passe_correct(basic(MDP)["Authorization"].replace("Basic", "basic"), MDP)
    assert not mot_de_passe_correct(None, MDP) and not mot_de_passe_correct("Basic", MDP)


def test_password_never_appears_in_responses(runtime):
    c = client(runtime)
    for chemin in ("/", "/api/status", "/api/reglages", "/api/journal"):
        assert MDP not in c.get(chemin, headers={**LAN, **basic(MDP)}).text


# --- essais limités ---
def test_too_many_wrong_attempts_block_even_the_right_password(runtime):
    horloge = [0.0]
    limite = LimiteEssais(maximum=5, fenetre=60, horloge=lambda: horloge[0])
    c = client(runtime, limite=limite)
    for _ in range(5):
        assert c.get("/api/status", headers={**LAN, **basic("faux")}).status_code == 401
    bloque = c.get("/api/status", headers={**LAN, **basic(MDP)})
    assert bloque.status_code == 429 and bloque.headers["retry-after"] == "60"
    horloge[0] += 61  # une minute plus tard
    assert c.get("/api/status", headers={**LAN, **basic(MDP)}).status_code == 200


def test_a_success_resets_the_counter(runtime):
    limite = LimiteEssais(maximum=3)
    c = client(runtime, limite=limite)
    for _ in range(2):
        c.get("/api/status", headers={**LAN, **basic("faux")})
    assert c.get("/api/status", headers={**LAN, **basic(MDP)}).status_code == 200
    for _ in range(2):
        c.get("/api/status", headers={**LAN, **basic("faux")})
    assert c.get("/api/status", headers={**LAN, **basic(MDP)}).status_code == 200  # 2 essais ratés seulement


def test_limiter_memory_is_bounded():
    limite = LimiteEssais(maximum=5)
    for i in range(3000):
        limite.echec(f"10.0.{i // 250}.{i % 250}")
    assert len(limite._echecs) <= 1001


# --- ce qui ne change pas ---
def test_foreign_origin_is_still_refused_even_with_the_password(runtime):
    c = client(runtime)
    reponse = c.post("/api/muet", json={"muet": True}, headers={**LAN, **basic(MDP), "Origin": "http://exemple.org"})
    assert reponse.status_code == 403 and runtime.settings.muet is False
    meme_origine = c.post("/api/muet", json={"muet": True}, headers={**LAN, **basic(MDP), "Origin": f"http://192.168.1.20:{PORT}"})
    assert meme_origine.status_code == 200


def test_local_mode_has_no_password_but_still_only_local_hosts(runtime):
    c = TestClient(create_app(runtime, PORT), base_url=f"http://127.0.0.1:{PORT}")
    assert c.get("/api/status", headers={"Host": f"127.0.0.1:{PORT}"}).json()["reseau"] is False
    assert c.get("/api/status", headers={"Host": f"192.168.1.20:{PORT}"}).status_code == 403
    assert c.get("/api/status", headers={"Host": "exemple.org"}).status_code == 403


def test_requests_without_credentials_never_lock_anyone_out(runtime):
    c = client(runtime, limite=LimiteEssais(maximum=3))
    for _ in range(20):  # le navigateur demande la page sans identifiants avant d'afficher la fenêtre de mot de passe
        assert c.get("/", headers=LAN).status_code == 401
    assert c.get("/", headers={**LAN, **basic(MDP)}).status_code == 200
