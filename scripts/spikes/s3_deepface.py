"""Essai S3 : DeepFace en local sur ce Mac (détection, empreinte, comparaison, vitesse).

DeepFace est volumineux (TensorFlow) : on l'installe à part, pas dans les dépendances de BeeDoo.

    pip install deepface
    python scripts/spikes/s3_deepface.py photo1.jpg [photo2.jpg]

Avec une seule photo : détecte les visages, calcule l'empreinte, mesure le temps.
Avec deux photos : indique aussi la distance entre le premier visage de chacune.
N'utilise que des photos locales. Ne les committe jamais (voir la section Vie privée du README).
"""

import argparse
import time

import numpy as np


def cosine_distance(a: list[float], b: list[float]) -> float:
    a, b = np.asarray(a), np.asarray(b)
    return float(1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("images", nargs="+")
    parser.add_argument("--model", default="Facenet512")
    parser.add_argument("--detector", default="opencv")
    parser.add_argument("--repeat", type=int, default=3, help="répétitions pour mesurer la vitesse")
    args = parser.parse_args()

    t = time.time()
    from deepface import DeepFace

    print(f"import deepface : {time.time() - t:.1f}s")

    embeddings = []
    for path in args.images:
        t = time.time()
        faces = DeepFace.represent(path, model_name=args.model, detector_backend=args.detector,
                                   enforce_detection=False)
        first = time.time() - t  # inclut le téléchargement et le chargement du modèle
        times = []
        for _ in range(args.repeat):
            t = time.time()
            DeepFace.represent(path, model_name=args.model, detector_backend=args.detector,
                               enforce_detection=False)
            times.append(time.time() - t)
        found = [f for f in faces if f.get("face_confidence", 0) > 0]
        print(f"{path}: {len(found)} visage(s) | 1er appel {first:.1f}s | ensuite {np.mean(times):.2f}s par image "
              f"| modèle={args.model} détecteur={args.detector}")
        if found:
            embeddings.append(found[0]["embedding"])
            print(f"   confiance={found[0]['face_confidence']:.2f} taille empreinte={len(found[0]['embedding'])}")

    if len(embeddings) == 2:
        print(f"distance cosinus entre les deux premiers visages : {cosine_distance(*embeddings):.3f}")


if __name__ == "__main__":
    main()
