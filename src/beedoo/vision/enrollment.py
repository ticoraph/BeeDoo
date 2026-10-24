"""Enrôlement d'une personne par la caméra, guidé comme dans un photomaton.

BeeDoo annonce à voix haute chaque pose (« Tourne doucement la tête vers ta gauche »), laisse un instant pour
la prendre, puis fait « Clic ! » et passe à la suivante. La page web affiche la même consigne en grand (utile
en mode muet). Les poses variées donnent des empreintes variées, donc une reconnaissance plus fiable (essai S3).

On ne garde que les empreintes (jamais les images). Seules les images où un visage assez grand est trouvé
comptent : chaque pose a deux essais, et BeeDoo dit ce qui manque (trop loin, personne en vue) avant le second.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from beedoo.vision.faces import MIN_FACE_PIXELS

log = logging.getLogger(__name__)

ESSAIS_PAR_POSE = 2
MIN_REUSSI = 3  # empreintes valides minimum pour que l'enrôlement compte


@dataclass(frozen=True)
class Pose:
    titre: str  # affiché dans la page
    dire: str   # dit par BeeDoo (phrases courtes, vocabulaire simple)


POSES = (
    Pose("Regarde BeeDoo, tout droit", "Regarde-moi droit dans les yeux."),
    Pose("Tourne doucement la tête vers ta gauche", "Tourne doucement la tête vers ta gauche. Pas trop !"),
    Pose("Tourne doucement la tête vers ta droite", "Maintenant, tourne doucement la tête vers ta droite."),
    Pose("Relève un peu le menton", "Relève un peu le menton, comme pour regarder le plafond."),
    Pose("Baisse un peu le menton", "Baisse un peu le menton, comme pour regarder tes pieds."),
    Pose("Fais un grand sourire !", "Regarde-moi et fais un grand sourire !"),
)

CLIC = "Clic ! "
INTRO = "Prends la pose ! Je te prends en photo, comme dans un photomaton. Mets-toi bien en face de moi."
FIN_BONNE = "C'est fini, bravo !"
FIN_RATEE = "Zut, je n'ai pas assez de photos. Approche-toi, mets-toi dans la lumière, et on recommence."
PROBLEMES = {
    "aucun_visage": "Je ne te vois pas. Mets-toi en face de moi.",
    "trop_petit": "Tu es trop loin. Approche-toi un peu.",
    "aucune_image": "Je n'ai pas reçu d'image. On réessaie.",
    "erreur": "Ça n'a pas marché. On réessaie.",
}


class Enrollment:
    def __init__(self, get_frame: Callable, recognizer, annoncer: Callable[[str], bool] | None = None,
                 poses: tuple[Pose, ...] = POSES, delai: float = 2.0, interval: float = 4.0,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        """`annoncer(texte)` fait dire le texte par le robot et rend True s'il a parlé (False : muet, erreur).

        `delai` : secondes laissées pour prendre la pose après l'annonce ; `interval` : idem quand BeeDoo n'a pas
        pu parler (la personne doit alors lire la page, il faut plus de temps).
        """
        self._get_frame = get_frame
        self._recognizer = recognizer
        self._annoncer = annoncer
        self._poses = poses
        self._delai = delai
        self._interval = interval
        self._sleep = sleep
        self._verrou = threading.Lock()
        self._annule = threading.Event()
        self._etat = self._neuf("libre")
        self._thread: threading.Thread | None = None

    def _neuf(self, etat: str) -> dict:
        return {"etat": etat, "ajoutes": 0, "total": len(self._poses), "essais": 0, "pose": None, "consigne": None,
                "derniere": None, "taille": None, "min_taille": MIN_FACE_PIXELS}

    @property
    def en_cours(self) -> bool:
        return self._etat["etat"] == "en_cours"

    def status(self) -> dict:
        return dict(self._etat)

    def start(self, name: str, apres: Callable[[str], None] | None = None) -> bool:
        """Lance l'enrôlement en arrière-plan. False si un autre est déjà en cours.

        `apres(name)` est appelé seulement si l'enrôlement réussit (par exemple pour enregistrer un consentement).
        """
        if not self._verrou.acquire(blocking=False):
            return False
        self._annule.clear()
        self._etat = self._neuf("en_cours")
        self._thread = threading.Thread(target=self._run, args=(name, apres), name="beedoo-enrolement", daemon=True)
        self._thread.start()
        return True

    def annuler(self) -> bool:
        """Demande l'arrêt de l'enrôlement en cours (les empreintes déjà prises restent). False s'il n'y en a pas."""
        if not self.en_cours:
            return False
        self._annule.set()
        return True

    def join(self, timeout: float = 5.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _dire(self, texte: str) -> bool:
        if self._annoncer is None:
            return False
        try:
            return bool(self._annoncer(texte))
        except Exception as erreur:
            log.warning("annonce d'enrôlement impossible (%s)", type(erreur).__name__)
            return False

    def _prendre(self, name: str) -> tuple[str, int | None]:
        statut, taille = "aucune_image", None
        try:
            frame = self._get_frame()
            if frame is not None:
                lecture = self._recognizer.enroll_image(name, frame)
                statut, taille = lecture.statut, lecture.taille
        except Exception as erreur:
            statut = "erreur"
            log.warning("image d'enrôlement ignorée (%s)", type(erreur).__name__)
        return statut, taille

    def _run(self, name: str, apres: Callable[[str], None] | None) -> None:
        try:
            self._dire(INTRO)
            self._sleep(self._delai)
            prefixe = ""
            for numero, pose in enumerate(self._poses):
                self._etat["pose"], self._etat["consigne"] = numero, pose.titre
                if prefixe != CLIC:  # on ne garde que le « Clic ! » de la pose précédente, pas son message d'erreur
                    prefixe = ""
                for _ in range(ESSAIS_PAR_POSE):
                    if self._annule.is_set():
                        break
                    parle = self._dire(prefixe + pose.dire)
                    self._sleep(self._delai if parle else self._interval)
                    if self._annule.is_set():
                        break
                    statut, taille = self._prendre(name)
                    self._etat["essais"] += 1
                    self._etat["derniere"], self._etat["taille"] = statut, taille
                    if statut == "ok":
                        self._etat["ajoutes"] += 1
                        prefixe = CLIC
                        break
                    prefixe = PROBLEMES.get(statut, PROBLEMES["erreur"]) + " "
                if self._annule.is_set():
                    break
            ajoutes = self._etat["ajoutes"]
            reussi = ajoutes >= min(MIN_REUSSI, len(self._poses)) and not self._annule.is_set()
            if reussi and apres is not None:
                try:
                    apres(name)
                except Exception as erreur:
                    log.warning("enrôlement : étape finale impossible (%s)", type(erreur).__name__)
            self._etat["pose"], self._etat["consigne"] = None, None
            if self._annule.is_set():
                etat = "annule"
            else:
                # Avant de rendre la main : la vision ne doit pas saluer par-dessus.
                self._dire(((prefixe if prefixe == CLIC else "") + FIN_BONNE) if reussi else FIN_RATEE)
                etat = "termine" if reussi else "echec"
            self._etat["etat"] = etat
            log.info("enrôlement fini (%s) : %d empreintes en %d essais", etat, ajoutes, self._etat["essais"])
        finally:
            self._verrou.release()
