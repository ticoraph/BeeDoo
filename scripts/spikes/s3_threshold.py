"""Essai S3 : choisir le seuil de reconnaissance à partir d'images étiquetées.

    python scripts/spikes/s3_threshold.py data/spikes/labeled

Les fichiers sont nommés <personne>_<pose>.jpg. Pour chaque image on garde le plus grand
visage (RetinaFace), on calcule l'empreinte Facenet512, puis on compare :
  - distances entre images de la MÊME personne (doivent être petites),
  - distances entre personnes DIFFÉRENTES (doivent être grandes),
  - reconnaissance « une image contre le reste » avec plusieurs seuils.
"""

import argparse
import itertools
from pathlib import Path

import numpy as np
from deepface import DeepFace



def cosine(a, b) -> float:
    return float(1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folder")
    parser.add_argument("--model", default="Facenet512")
    parser.add_argument("--detector", default="retinaface")
    parser.add_argument("--people", nargs="*", help="ne garder que ces personnes (préfixe des fichiers)")
    parser.add_argument("--quiet", action="store_true", help="n'affiche pas le détail par image")
    args = parser.parse_args()

    MODEL, DETECTOR = args.model, args.detector
    print(f"modèle={MODEL} détecteur={DETECTOR}")
    samples = []  # (personne, pose, empreinte)
    for path in sorted(Path(args.folder).glob("*.jpg")):
        person, pose = path.stem.split("_", 1)
        if args.people and person not in args.people:
            continue
        faces = [f for f in DeepFace.represent(str(path), model_name=MODEL, detector_backend=DETECTOR,
                                               enforce_detection=False) if f["face_confidence"] > 0]
        if not faces:
            print(f"{path.name}: aucun visage")
            continue
        biggest = max(faces, key=lambda f: f["facial_area"]["w"] * f["facial_area"]["h"])
        area = biggest["facial_area"]
        if not args.quiet:
            print(f"{path.name}: {len(faces)} visage(s), retenu {area['w']}x{area['h']}px conf={biggest['face_confidence']:.2f}")
        samples.append((person, pose, np.array(biggest["embedding"])))

    people = sorted({p for p, _, _ in samples})
    if len(people) == 1:  # une seule personne : stabilité selon la pose, par rapport à la pose de face
        ref = next(e for _, pose, e in samples if pose == "face1")
        print("\nDistance de chaque pose à la pose de face (face1) :")
        for _, pose, emb in samples:
            print(f"  {pose:7s} {cosine(ref, emb):.2f}")
        return

    same, diff = [], []
    for (p1, _, e1), (p2, _, e2) in itertools.combinations(samples, 2):
        (same if p1 == p2 else diff).append(cosine(e1, e2))
    if not same or not diff:
        print("Il faut au moins deux personnes avec plusieurs images chacune.")
        return
    print(f"\nMême personne  ({len(same):2d} paires) : min {min(same):.2f}  moyenne {np.mean(same):.2f}  max {max(same):.2f}")
    print(f"Personnes diff.({len(diff):2d} paires) : min {min(diff):.2f}  moyenne {np.mean(diff):.2f}  max {max(diff):.2f}")
    print(f"Marge entre la pire paire identique et la meilleure paire différente : {min(diff) - max(same):+.2f}")

    print("\nReconnaissance d'une image contre toutes les autres (plus proche voisine) :")
    print("seuil | bien reconnues | confondues avec un autre | inconnues")
    for threshold in (0.20, 0.25, 0.30, 0.35, 0.40, 0.50):
        good = wrong = unknown = 0
        for i, (person, _, emb) in enumerate(samples):
            others = [(cosine(emb, e), p) for j, (p, _, e) in enumerate(samples) if j != i]
            distance, nearest = min(others)
            if distance > threshold:
                unknown += 1
            elif nearest == person:
                good += 1
            else:
                wrong += 1
        print(f" {threshold:.2f} | {good:2d}/{len(samples)}          | {wrong:2d}                       | {unknown:2d}")


if __name__ == "__main__":
    main()
