"""Prend une photo avec la caméra du Reachy Mini et la sauvegarde en JPEG.

Nécessite la dépendance optionnelle OpenCV :
    pip install reachy_mini[opencv]

Lancer :
    python scripts/take_picture.py
    python scripts/take_picture.py --output photo.jpg
"""

import argparse
import sys
import time

try:
    import cv2
except ImportError:
    print("Erreur : OpenCV est requis pour ce script mais n'est pas installé.")
    print("Installe-le avec : pip install reachy_mini[opencv]")
    sys.exit(1)

from reachy_mini import ReachyMini

TIMEOUT = 20  # secondes d'attente max pour obtenir une image


def main(backend: str, output_file: str) -> None:
    with ReachyMini(media_backend=backend) as mini:
        print("En attente d'une image de la caméra...")
        start_time = time.time()
        frame = mini.media.get_frame()
        while frame is None:
            if time.time() - start_time > TIMEOUT:
                print(f"Timeout : aucune image reçue en {TIMEOUT}s.")
                sys.exit(1)
            time.sleep(1)
            frame = mini.media.get_frame()

        cv2.imwrite(output_file, frame)
        print(f"📸  Photo enregistrée dans {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prend une photo avec la caméra du Reachy Mini."
    )
    parser.add_argument(
        "--backend",
        type=str,
        choices=["default", "local", "webrtc"],
        default="default",
        help="Backend média à utiliser.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="beedoo_picture.jpg",
        help="Chemin du fichier de sortie (défaut : beedoo_picture.jpg).",
    )

    args = parser.parse_args()
    main(backend=args.backend, output_file=args.output)
