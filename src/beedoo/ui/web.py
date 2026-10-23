"""Interface web locale de BeeDoo (FastAPI, `127.0.0.1` uniquement).

Elle affiche l'état et permet de couper l'écoute. Elle ne saisit ni n'affiche aucune clé API.
Deux protections contre un site ouvert dans le même navigateur qui tenterait de commander BeeDoo :
l'en-tête `Host` doit être l'adresse locale (contre le DNS rebinding) et un en-tête `Origin`, s'il
existe, doit être celui de la page elle-même.
"""

import base64
import binascii
import logging
import secrets
import threading
import time

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from beedoo.gestures.library import GESTES
from beedoo.memory.store import MAX_FAITS
from beedoo import logs, robot_volume
from beedoo.runtime import Runtime
from beedoo.settings import VOIX
from beedoo.ui.page import PAGE
from beedoo.vision.faces import MIN_FACE_PIXELS, person_id

log = logging.getLogger(__name__)

HOST = "127.0.0.1"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
MOT_DE_PASSE_MIN = 8


def acces_web(hote: str, mot_de_passe: str) -> tuple[str, str | None]:
    """(adresse d'écoute, mot de passe exigé ou None).

    Par défaut l'interface n'écoute que sur cet ordinateur. Une autre adresse (réseau local) n'est acceptée
    qu'avec un mot de passe d'au moins 8 caractères ; sinon on reste sur cet ordinateur.
    """
    hote = (hote or HOST).strip()
    if hote in LOOPBACK:
        return HOST, None
    if len(mot_de_passe) < MOT_DE_PASSE_MIN:
        log.error("accès réseau refusé : BEEDOO_WEB_PASSWORD doit faire au moins %d caractères. "
                  "L'interface reste limitée à cet ordinateur.", MOT_DE_PASSE_MIN)
        return HOST, None
    log.warning("interface web ouverte au réseau local, protégée par mot de passe (connexion non chiffrée)")
    return hote, mot_de_passe


class LimiteEssais:
    """Bloque une adresse après trop d'essais de mot de passe ratés dans une courte durée."""

    def __init__(self, maximum: int = 5, fenetre: float = 60.0, horloge=time.monotonic) -> None:
        self._maximum, self._fenetre, self._horloge = maximum, fenetre, horloge
        self._echecs: dict[str, list[float]] = {}
        self._verrou = threading.Lock()

    def _recents(self, cle: str) -> list[float]:
        limite = self._horloge() - self._fenetre
        recents = [t for t in self._echecs.get(cle, []) if t > limite]
        if recents:
            self._echecs[cle] = recents
        else:
            self._echecs.pop(cle, None)
        return recents

    def bloque(self, cle: str) -> bool:
        with self._verrou:
            return len(self._recents(cle)) >= self._maximum

    def echec(self, cle: str) -> None:
        with self._verrou:
            if len(self._echecs) > 1000:  # une machine qui défile les adresses ne remplit pas la mémoire
                self._echecs.clear()
            self._echecs.setdefault(cle, []).append(self._horloge())

    def succes(self, cle: str) -> None:
        with self._verrou:
            self._echecs.pop(cle, None)


class MuetRequest(BaseModel):
    muet: bool


class GesteRequest(BaseModel):
    nom: str


class ReglagesRequest(BaseModel):
    """Chaque champ est facultatif : on ne change que ce qui est envoyé."""

    vitesse: float | None = Field(default=None, ge=0.5, le=1.5)
    voix: str | None = None
    volume: int | None = Field(default=None, ge=0, le=100)
    suivi: bool | None = None
    ville: str | None = Field(default=None, max_length=80)


class MiniAppRequest(BaseModel):
    active: bool


class PrenomRequest(BaseModel):
    prenom: str


class AjoutRequest(BaseModel):
    prenom: str
    memoire: bool = False  # la personne accepte que BeeDoo se souvienne de ce qu'elle dit


class ConsentementRequest(BaseModel):
    accepte: bool


class FaitsRequest(BaseModel):
    faits: list[str] = Field(max_length=MAX_FAITS)


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


def mot_de_passe_correct(en_tete: str | None, attendu: str) -> bool:
    """Vrai si l'en-tête `Authorization: Basic …` porte le bon mot de passe (l'identifiant est libre)."""
    if not en_tete or not en_tete.lower().startswith("basic "):
        return False
    try:
        fourni = base64.b64decode(en_tete[6:].strip(), validate=True).decode("utf-8").partition(":")[2]
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    return secrets.compare_digest(fourni.encode(), attendu.encode())  # temps constant


def create_app(runtime: Runtime, port: int, mot_de_passe: str | None = None,
               limite: LimiteEssais | None = None) -> FastAPI:
    """`mot_de_passe` non nul = accès réseau : mot de passe exigé et adresse d'appel libre (sinon cet ordinateur seul)."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    reseau = mot_de_passe is not None
    limite = limite or LimiteEssais()
    hotes_permis = {f"{HOST}:{port}", f"localhost:{port}"}

    @app.middleware("http")
    async def verifier_origine(request: Request, call_next):
        hote = request.headers.get("host", "")
        origine = request.headers.get("origin")
        # Cet ordinateur seul : l'adresse d'appel doit être locale (contre le « DNS rebinding »). Accès réseau :
        # l'adresse est libre, c'est le mot de passe qui protège. Dans les deux cas, une requête venue d'un
        # autre site (en-tête Origin différent de la page) est refusée.
        if (not reseau and hote not in hotes_permis) or (origine is not None and origine != f"http://{hote}"):
            return JSONResponse({"erreur": "refusé"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.middleware("http")
    async def authentifier(request: Request, call_next):
        if not reseau:
            return await call_next(request)
        client = request.client.host if request.client else "inconnu"
        if limite.bloque(client):
            return JSONResponse({"erreur": "trop d'essais, réessaie dans une minute"}, status_code=429,
                                headers={"Retry-After": "60"})
        fourni = request.headers.get("authorization")
        if not mot_de_passe_correct(fourni, mot_de_passe):
            if fourni:  # seul un mot de passe fourni ET faux compte : le navigateur commence toujours sans rien
                limite.echec(client)
            return JSONResponse({"erreur": "mot de passe requis"}, status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="BeeDoo", charset="UTF-8"'})
        limite.succes(client)
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse)
    def accueil() -> str:
        return PAGE

    @app.get("/api/status")
    def status() -> dict:
        return {**runtime.status(), "reseau": reseau}

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

    def reglages() -> dict:
        return {"vitesse": runtime.settings.vitesse, "voix": runtime.settings.voix or runtime.config.tts_voice,
                "voix_possibles": list(VOIX), "suivi": runtime.settings.suivi, "ville": runtime.settings.ville, "volume": robot_volume.lire(runtime.config.daemon_url)}

    @app.get("/api/reglages")
    def lire_reglages() -> dict:
        return reglages()

    @app.post("/api/reglages")
    def changer_reglages(requete: ReglagesRequest) -> dict:
        if requete.voix is not None and requete.voix not in VOIX:
            raise HTTPException(status_code=422, detail="voix inconnue")
        if requete.volume is not None and not robot_volume.regler(runtime.config.daemon_url, requete.volume):
            raise HTTPException(status_code=502, detail="le robot ne répond pas")
        runtime.set_reglages(requete.vitesse, requete.voix, requete.suivi, requete.ville)
        return reglages()

    @app.get("/api/miniapps")
    def miniapps() -> dict:
        coupees = set(runtime.settings.miniapps_desactivees)
        return {"miniapps": [{"nom": m.nom, "titre": m.titre, "active": m.nom not in coupees}
                             for m in runtime.miniapps]}

    @app.post("/api/miniapps/{nom}")
    def activer_miniapp(nom: str, requete: MiniAppRequest) -> dict:
        try:
            runtime.set_miniapp(nom, requete.active)
        except KeyError:
            raise HTTPException(status_code=404, detail="mini-application inconnue") from None
        return miniapps()

    @app.post("/api/test-voix", status_code=202)
    def tester_la_voix() -> dict:
        if runtime.speaker is None:
            raise HTTPException(status_code=503, detail="robot non connecté")
        if runtime.settings.muet:
            raise HTTPException(status_code=409, detail="BeeDoo est en mode muet")
        threading.Thread(target=runtime.speaker.say, args=("Bonjour ! Voilà ma voix. Elle te plaît ?",),
                         name="beedoo-test-voix", daemon=True).start()
        return {"ok": True}

    @app.get("/api/journal")
    def journal(depuis: int = 0) -> dict:
        """Événements récents (messages de BeeDoo, sans clé ni chemin personnel). Perdus à l'arrêt."""
        lignes, dernier = logs.JOURNAL.depuis(max(depuis, 0))
        return {"lignes": lignes, "dernier": dernier}

    @app.get("/api/echange")
    def echange() -> dict:
        """Dernière phrase entendue et dite, tant que la conversation dure (jamais écrite sur le disque)."""
        memoire = runtime.conversation.info_memoire() if runtime.conversation is not None else None
        return {"echange": runtime.echange, "memoire": memoire}

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
        memoire = runtime.memoire
        liste = [] if faces is None else [
            {"id": pid, "nom": faces.display_name(pid), "empreintes": len(faces.embeddings(pid)),
             "memoire": memoire is not None and memoire.consentement(pid),
             "faits": 0 if memoire is None else len(memoire.faits(pid)),
             "conversations": 0 if memoire is None else len(memoire.conversations(pid))}
            for pid in faces.people()]
        enrolement = runtime.enrolement
        return {"personnes": liste, "camera": enrolement is not None,
                "enrolement": None if enrolement is None else enrolement.status()}

    @app.post("/api/personnes", status_code=202)
    def ajouter(requete: AjoutRequest) -> dict:
        prenom = prenom_valide(requete.prenom)
        if runtime.enrolement is None:
            raise HTTPException(status_code=503, detail="caméra indisponible")
        memoire = runtime.memoire
        # Le consentement n'est enregistré que si l'enrôlement réussit (pas de dossier orphelin).
        apres = (lambda nom: memoire.set_consentement(nom, True)) if requete.memoire and memoire is not None else None
        if not runtime.enrolement.start(prenom, apres):
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

    def magasin():
        if runtime.memoire is None:
            raise HTTPException(status_code=503, detail="mémoire indisponible")
        return runtime.memoire

    @app.put("/api/personnes/{pid}/memoire")
    def consentement(pid: str, requete: ConsentementRequest) -> dict:
        magasin().set_consentement(personne(pid), requete.accepte)
        return {"memoire": requete.accepte}

    @app.get("/api/personnes/{pid}/souvenirs")
    def souvenirs(pid: str) -> dict:
        memoire = magasin()
        pid = personne(pid)
        return {"memoire": memoire.consentement(pid), "faits": memoire.faits(pid),
                "conversations": len(memoire.conversations(pid))}

    @app.put("/api/personnes/{pid}/souvenirs")
    def corriger_souvenirs(pid: str, requete: FaitsRequest) -> dict:
        try:
            ecrits = magasin().ecrire_faits(personne(pid), [f for f in requete.faits if f.strip()])
        except ValueError:
            raise HTTPException(status_code=422, detail="un souvenir est refusé (trop court, trop long, ou secret)") from None
        return {"faits": ecrits}

    @app.delete("/api/personnes/{pid}/souvenirs")
    def effacer_souvenirs(pid: str) -> dict:
        magasin().effacer(personne(pid))
        log.info("les souvenirs d'une personne ont été effacés")
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

    def __init__(self, runtime: Runtime, port: int, host: str = HOST, mot_de_passe: str | None = None) -> None:
        self.port = port
        self.host = host
        config = uvicorn.Config(create_app(runtime, port, mot_de_passe), host=host, port=port,
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
        log.info("interface web : http://%s:%d", self.host, self.port)

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
