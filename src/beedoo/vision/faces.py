"""Reconnaissance de visage locale (DeepFace). Rien ne quitte la machine.

- Les empreintes (vecteurs de nombres) sont stockées dans `data/personnes/<id>/visage.json`.
  Les images ne sont jamais conservées.
- Plusieurs empreintes par personne (poses différentes) : on compare à la plus proche.
- Une personne n'est reconnue que si elle est assez proche ET nettement plus proche que
  la deuxième personne la plus proche ; sinon BeeDoo considère qu'il ne la connaît pas.

DeepFace est une dépendance optionnelle (`pip install deepface`) : seule l'extraction
d'empreintes en a besoin, la comparaison et le stockage non.

SEUILS PROVISOIRES : valeurs publiées par DeepFace, pas encore calibrées sur nos images.
Voir docs/DECISIONS.md (essai S3).
"""

import json
import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_MODEL = "ArcFace"
DEFAULT_DETECTOR = "retinaface"
# Distance cosinus en dessous de laquelle deux empreintes sont « la même personne » (provisoire).
THRESHOLDS = {"ArcFace": 0.68, "Facenet": 0.40, "Facenet512": 0.30}
MIN_MARGIN = 0.05       # écart minimal avec la deuxième personne la plus proche
MIN_FACE_PIXELS = 90    # plus petit côté de la boîte du visage ; en dessous on ignore (trop loin, parasite)


def cosine_distance(a, b) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return float(1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def person_id(name: str) -> str:
    """Identifiant sûr pour un nom de dossier : minuscules, sans accent, lettres, chiffres et tirets."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    if not slug:
        raise ValueError(f"nom de personne invalide : {name!r}")
    return slug[:40]


@dataclass(frozen=True)
class Match:
    person: str | None       # None = personne inconnue
    distance: float | None   # distance à la personne la plus proche (None si galerie vide)
    margin: float | None     # écart avec la deuxième personne la plus proche (None si une seule)
    reason: str = ""         # "", "trop_loin", "ambigu", "aucune_personne"


def best_match(embedding, gallery: dict[str, list[list[float]]], threshold: float,
               min_margin: float = MIN_MARGIN) -> Match:
    """Cherche la personne connue la plus proche, ou conclut « inconnu »."""
    per_person = sorted(
        (min(cosine_distance(embedding, e) for e in embeddings), person)
        for person, embeddings in gallery.items() if embeddings
    )
    if not per_person:
        return Match(None, None, None, "aucune_personne")
    distance, person = per_person[0]
    margin = per_person[1][0] - distance if len(per_person) > 1 else None
    if distance > threshold:
        return Match(None, distance, margin, "trop_loin")
    if margin is not None and margin < min_margin:
        return Match(None, distance, margin, "ambigu")
    return Match(person, distance, margin)


class FaceStore:
    """Empreintes de visages enregistrées, un fichier par personne."""

    def __init__(self, data_dir: Path, model: str = DEFAULT_MODEL):
        self.root = Path(data_dir) / "personnes"
        self.model = model

    def _file(self, person: str) -> Path:
        return self.root / person_id(person) / "visage.json"

    def people(self) -> list[str]:
        return sorted(p.parent.name for p in self.root.glob("*/visage.json"))

    def embeddings(self, person: str) -> list[list[float]]:
        file = self._file(person)
        if not file.exists():
            return []
        data = json.loads(file.read_text())
        if data.get("model") != self.model:  # empreintes d'un autre modèle : inutilisables
            return []
        return data["embeddings"]

    def gallery(self) -> dict[str, list[list[float]]]:
        return {person: self.embeddings(person) for person in self.people()}

    def add(self, person: str, new_embeddings: list[list[float]]) -> int:
        file = self._file(person)
        file.parent.mkdir(parents=True, exist_ok=True)
        embeddings = self.embeddings(person) + [list(map(float, e)) for e in new_embeddings]
        file.write_text(json.dumps({"model": self.model, "embeddings": embeddings}))
        return len(embeddings)

    def forget(self, person: str) -> None:
        """Efface tout ce que BeeDoo sait de cette personne (le dossier entier)."""
        folder = self._file(person).parent
        if folder.exists():
            shutil.rmtree(folder)


def extract_embedding(image, model: str = DEFAULT_MODEL, detector: str = DEFAULT_DETECTOR,
                      min_face_pixels: int = MIN_FACE_PIXELS) -> list[float] | None:
    """Empreinte du plus grand visage de l'image (chemin ou tableau BGR), ou None.

    Ignore les visages trop petits (parasites, personnes au loin).
    """
    from deepface import DeepFace  # import tardif : dépendance optionnelle et lourde

    faces = [f for f in DeepFace.represent(image, model_name=model, detector_backend=detector,
                                           enforce_detection=False) if f["face_confidence"] > 0]
    if not faces:
        return None
    biggest = max(faces, key=lambda f: f["facial_area"]["w"] * f["facial_area"]["h"])
    area = biggest["facial_area"]
    if min(area["w"], area["h"]) < min_face_pixels:
        return None
    return list(biggest["embedding"])


class FaceRecognizer:
    def __init__(self, store: FaceStore, detector: str = DEFAULT_DETECTOR, threshold: float | None = None,
                 min_margin: float = MIN_MARGIN):
        self.store = store
        self.detector = detector
        self.threshold = threshold if threshold is not None else THRESHOLDS[store.model]
        self.min_margin = min_margin

    def enroll(self, person: str, images) -> int:
        """Enregistre une empreinte par image où un visage assez grand est trouvé. Retourne le nombre ajouté."""
        found = [e for e in (extract_embedding(i, self.store.model, self.detector) for i in images) if e]
        if found:
            self.store.add(person, found)
        return len(found)

    def identify(self, image) -> Match:
        embedding = extract_embedding(image, self.store.model, self.detector)
        if embedding is None:
            return Match(None, None, None, "aucun_visage")
        return best_match(embedding, self.store.gallery(), self.threshold, self.min_margin)
