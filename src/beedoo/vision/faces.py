"""Reconnaissance de visage locale (DeepFace). Rien ne quitte la machine.

- Les empreintes (vecteurs de nombres) sont stockées dans `data/personnes/<id>/visage.json`.
  Les images ne sont jamais conservées.
- Plusieurs empreintes par personne (poses différentes) : on compare à la plus proche.
- Une personne n'est reconnue que si elle est assez proche ET nettement plus proche que
  la deuxième personne la plus proche ; sinon BeeDoo considère qu'il ne la connaît pas.

DeepFace est une dépendance optionnelle (`pip install deepface`) : seule l'extraction
d'empreintes en a besoin, la comparaison et le stockage non.

SEUILS PROVISOIRES : valeurs publiées par DeepFace, pas encore calibrées sur nos images.
Voir l'essai S3 (scripts/spikes/s3_threshold.py).
"""

import json
import os
import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from beedoo.donnees import proteger_fichier

DEFAULT_MODEL = "ArcFace"
DEFAULT_DETECTOR = "retinaface"
# Distance cosinus en dessous de laquelle deux empreintes sont « la même personne » (provisoire).
THRESHOLDS = {"ArcFace": 0.68, "Facenet": 0.40, "Facenet512": 0.30}
MIN_MARGIN = 0.05       # écart minimal avec la deuxième personne la plus proche
MIN_FACE_PIXELS = 60    # plus petit côté de la boîte du visage ; en dessous : « trop loin » (mesuré : reconnaissance
                        # excellente à 74 px sur une image 1920x1080, distance 0,02)


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
    reason: str = ""         # "", "trop_loin", "ambigu", "aucune_personne", "aucun_visage", "trop_petit"
    taille: int | None = None  # plus petit côté du visage vu, en pixels (None si aucun visage)


@dataclass(frozen=True)
class Lecture:
    """Ce que la caméra a donné pour un enrôlement."""

    statut: str              # "ok", "aucun_visage" ou "trop_petit"
    taille: int | None = None


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

    def _read(self, person: str) -> dict:
        try:
            return json.loads(self._file(person).read_text())
        except (OSError, ValueError):
            return {}

    def _write(self, person: str, data: dict) -> None:
        """Écriture atomique : la boucle de vision lit ces fichiers pendant que l'interface les modifie."""
        file = self._file(person)
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data))
        os.chmod(tmp, 0o600)
        os.replace(tmp, file)
        proteger_fichier(file, self.root.parent)  # dossiers de la personne et de data/ en 700

    def display_name(self, person: str) -> str:
        """Prénom tel qu'il a été saisi (« Léa »), à défaut l'identifiant mis en majuscule initiale."""
        return self._read(person).get("nom") or person_id(person).replace("-", " ").title()

    def add(self, person: str, new_embeddings: list[list[float]]) -> int:
        data = self._read(person)
        embeddings = self.embeddings(person) + [list(map(float, e)) for e in new_embeddings]
        self._write(person, {"model": self.model, "nom": data.get("nom") or person.strip(),
                             "embeddings": embeddings})
        return len(embeddings)

    def rename(self, old: str, new: str) -> str:
        """Change le prénom d'une personne. Retourne le nouvel identifiant."""
        old_id, new_id = person_id(old), person_id(new)
        if not self._file(old).exists():
            raise KeyError(old)
        if new_id != old_id and self._file(new).parent.exists():
            raise ValueError("une personne porte déjà ce prénom")
        data = self._read(old)
        data["nom"] = new.strip()
        if new_id != old_id:
            self._file(old).parent.rename(self._file(new).parent)
        self._write(new, data)
        return new_id

    def forget(self, person: str) -> None:
        """Efface tout ce que BeeDoo sait de cette personne (le dossier entier)."""
        folder = self._file(person).parent
        if folder.exists():
            shutil.rmtree(folder)


@dataclass(frozen=True)
class Visage:
    embedding: list[float]
    taille: int  # plus petit côté de la boîte, en pixels


def detect_face(image, model: str = DEFAULT_MODEL, detector: str = DEFAULT_DETECTOR) -> Visage | None:
    """Le plus grand visage de l'image (chemin ou tableau BGR) avec son empreinte, ou None s'il n'y en a pas."""
    from deepface import DeepFace  # import tardif : dépendance lourde

    faces = [f for f in DeepFace.represent(image, model_name=model, detector_backend=detector,
                                           enforce_detection=False) if f["face_confidence"] > 0]
    if not faces:
        return None
    biggest = max(faces, key=lambda f: f["facial_area"]["w"] * f["facial_area"]["h"])
    area = biggest["facial_area"]
    return Visage(list(biggest["embedding"]), min(area["w"], area["h"]))


def extract_embedding(image, model: str = DEFAULT_MODEL, detector: str = DEFAULT_DETECTOR,
                      min_face_pixels: int = MIN_FACE_PIXELS) -> list[float] | None:
    """Empreinte du plus grand visage de l'image, ou None (aucun visage, ou trop petit)."""
    face = detect_face(image, model, detector)
    return face.embedding if face is not None and face.taille >= min_face_pixels else None


class FaceRecognizer:
    def __init__(self, store: FaceStore, detector: str = DEFAULT_DETECTOR, threshold: float | None = None,
                 min_margin: float = MIN_MARGIN, min_face_pixels: int = MIN_FACE_PIXELS):
        self.store = store
        self.detector = detector
        self.threshold = threshold if threshold is not None else THRESHOLDS[store.model]
        self.min_margin = min_margin
        self.min_face_pixels = min_face_pixels

    def enroll_image(self, person: str, image) -> Lecture:
        """Enregistre l'empreinte du visage de l'image s'il est assez grand, et dit ce qui s'est passé."""
        face = detect_face(image, self.store.model, self.detector)
        if face is None:
            return Lecture("aucun_visage")
        if face.taille < self.min_face_pixels:
            return Lecture("trop_petit", face.taille)
        self.store.add(person, [face.embedding])
        return Lecture("ok", face.taille)

    def enroll(self, person: str, images) -> int:
        """Enregistre une empreinte par image où un visage assez grand est trouvé. Retourne le nombre ajouté."""
        return sum(self.enroll_image(person, i).statut == "ok" for i in images)

    def identify(self, image) -> Match:
        face = detect_face(image, self.store.model, self.detector)
        if face is None:
            return Match(None, None, None, "aucun_visage")
        if face.taille < self.min_face_pixels:
            return Match(None, None, None, "trop_petit", face.taille)
        match = best_match(face.embedding, self.store.gallery(), self.threshold, self.min_margin)
        return Match(match.person, match.distance, match.margin, match.reason, face.taille)
