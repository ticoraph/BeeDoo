"""Interface web locale de BeeDoo (FastAPI, `127.0.0.1` uniquement).

Elle affiche l'état et permet de couper l'écoute. Elle ne saisit ni n'affiche aucune clé API.
Deux protections contre un site ouvert dans le même navigateur qui tenterait de commander BeeDoo :
l'en-tête `Host` doit être l'adresse locale (contre le DNS rebinding) et un en-tête `Origin`, s'il
existe, doit être celui de la page elle-même.
"""

import logging
import threading
import time

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from beedoo.gestures.library import GESTES
from beedoo.runtime import Runtime
from beedoo.ui.page import PAGE
from beedoo.vision.faces import MIN_FACE_PIXELS, person_id

log = logging.getLogger(__name__)

HOST = "127.0.0.1"


class MuetRequest(BaseModel):
    muet: bool


class GesteRequest(BaseModel):
    nom: str


class PrenomRequest(BaseModel):
    prenom: str


def prenom_valide(valeur: str) -> str:
    """Prénom nettoyé (1 à 40 caractères avec au moins une lettre ou un chiffre), sinon erreur 422."""
    prenom = " ".join(valeur.split())
    try:
        if not prenom or len(prenom) > 40:
            raise ValueError
        person_id(prenom)
    except ValueError:
        raise HTTPException(status_code=422, detail="prénom invalide") from None
    return prenom


def create_app(runtime: Runtime, port: int) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    hotes_permis = {f"{HOST}:{port}", f"localhost:{port}"}

    @app.middleware("http")
    async def verifier_origine(request: Request, call_next):
        hote = request.headers.get("host", "")
        origine = request.headers.get("origin")
        if hote not in hotes_permis or (origine is not None and origine != f"http://{hote}"):
            return JSONResponse({"erreur": "refusé"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/", response_class=HTMLResponse)
    def accueil() -> str:
        return PAGE

    @app.get("/api/status")
    def status() -> dict:
        return runtime.status()

    @app.post("/api/muet")
    def muet(requete: MuetRequest) -> dict:
        runtime.set_muet(requete.muet)
        return runtime.status()

    @app.get("/api/gestes")
    def gestes() -> dict:
        player = runtime.gestes
        return {"gestes": list(GESTES), "disponible": player is not None,
                "occupe": player is not None and player.occupe}

    @app.post("/api/geste")
    def geste(requete: GesteRequest) -> dict:
        if requete.nom not in GESTES:
            raise HTTPException(status_code=404, detail="geste inconnu")
        if runtime.gestes is None:
            raise HTTPException(status_code=503, detail="robot non connecté")
        if not runtime.gestes.play(requete.nom):
            raise HTTPException(status_code=409, detail="un geste est déjà en cours")
        return {"ok": True}

    def personne(pid: str) -> str:
        """Identifiant d'une personne connue, sinon 404 (aucun chemin construit à partir d'un texte brut)."""
        if runtime.faces is None or pid not in runtime.faces.people():
            raise HTTPException(status_code=404, detail="personne inconnue")
        return pid

    @app.get("/api/vision")
    def vision() -> dict:
        """Ce que BeeDoo voit : de quoi dire à la personne quoi faire (approche-toi, ajoute-toi…)."""
        if runtime.vision is None:
            return {"statut": "indisponible", "min_taille": MIN_FACE_PIXELS}
        lecture = runtime.vision.status()
        pid = lecture.pop("personne")
        if pid is not None and runtime.faces is not None:
            lecture["nom"] = runtime.faces.display_name(pid)
        return {**lecture, "min_taille": MIN_FACE_PIXELS}

    @app.get("/api/personnes")
    def personnes() -> dict:
        faces = runtime.faces
        liste = [] if faces is None else [
            {"id": pid, "nom": faces.display_name(pid), "empreintes": len(faces.embeddings(pid))}
            for pid in faces.people()]
        enrolement = runtime.enrolement
        return {"personnes": liste, "camera": enrolement is not None,
                "enrolement": None if enrolement is None else enrolement.status()}

    @app.post("/api/personnes", status_code=202)
    def ajouter(requete: PrenomRequest) -> dict:
        prenom = prenom_valide(requete.prenom)
        if runtime.enrolement is None:
            raise HTTPException(status_code=503, detail="caméra indisponible")
        if not runtime.enrolement.start(prenom):
            raise HTTPException(status_code=409, detail="un enrôlement est déjà en cours")
        return {"ok": True}

    @app.patch("/api/personnes/{pid}")
    def renommer(pid: str, requete: PrenomRequest) -> dict:
        pid = personne(pid)
        try:
            runtime.faces.rename(pid, prenom_valide(requete.prenom))
        except ValueError:
            raise HTTPException(status_code=409, detail="ce prénom existe déjà") from None
        if runtime.greeter is not None:
            runtime.greeter.forget(pid)
        return {"ok": True}

    @app.delete("/api/personnes/{pid}")
    def effacer(pid: str) -> dict:
        pid = personne(pid)
        runtime.faces.forget(pid)
        if runtime.greeter is not None:
            runtime.greeter.forget(pid)
        log.info("une personne a été effacée")
        return {"ok": True}

    return app


class WebServer:
    """Serveur uvicorn dans un thread, arrêtable proprement."""

    def __init__(self, runtime: Runtime, port: int) -> None:
        self.port = port
        config = uvicorn.Config(create_app(runtime, port), host=HOST, port=port,
                                log_level="warning", access_log=False)
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._run, name="beedoo-web", daemon=True)

    def _run(self) -> None:
        try:
            self._server.run()
        except SystemExit:
            # uvicorn quitte ainsi quand il ne peut pas écouter ; start() s'en aperçoit et lève OSError.
            log.warning("le serveur web s'est arrêté (port %d)", self.port)

    def start(self) -> None:
        """Démarre le serveur ; lève OSError s'il n'a pas pu écouter (port occupé par exemple)."""
        self._thread.start()
        deadline = time.monotonic() + 5
        while not self._server.started:
            if not self._thread.is_alive() or time.monotonic() > deadline:
                self._server.should_exit = True
                raise OSError(f"le serveur web n'a pas démarré sur le port {self.port}")
            time.sleep(0.05)
        log.info("interface web : http://%s:%d", HOST, self.port)

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
