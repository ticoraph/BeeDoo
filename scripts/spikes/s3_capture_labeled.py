"""Essai S3 : capture guidée d'images étiquetées avec la caméra du robot.

    python scripts/spikes/s3_capture_labeled.py personne1 personne2

Pour chaque personne : un message vocal demande de se placer devant le robot, puis
6 images sont prises avec des consignes de pose dites à voix haute (macOS `say`)
et un bip à chaque prise. Les images vont dans data/spikes/labeled/<personne>_<pose>.jpg
(ignoré par git : ce sont des visages, ne les committe jamais).
"""

import argparse
import subprocess
import time
from pathlib import Path

import cv2

from reachy_mini import ReachyMini

REPO_ROOT = Path(__file__).resolve().parents[2]
POSES = [
    ("face1", "Regarde le robot, de face."),
    ("face2", "Toujours de face, un peu plus loin."),
    ("gauche", "Tourne la tête vers la gauche."),
    ("droite", "Tourne la tête vers la droite."),
    ("haut", "Lève un peu la tête."),
    ("bas", "Baisse un peu la tête."),
]


def say(text: str) -> None:
    subprocess.run(["say", "-v", "Thomas", text], check=False)


def beep() -> None:
    subprocess.run(["afplay", "/System/Library/Sounds/Pop.aiff"], check=False)


def fresh_frame(mini, wait: float = 0.6):
    """Image la plus récente après un court délai (la caméra a un tampon d'images)."""
    time.sleep(wait)
    frame = None
    for _ in range(10):
        newer = mini.media.get_frame()
        if newer is not None:
            frame = newer
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("people", nargs="+")
    parser.add_argument("--pause", type=float, default=15, help="secondes pour changer de personne")
    args = parser.parse_args()

    out_dir = REPO_ROOT / "data" / "spikes" / "labeled"
    out_dir.mkdir(parents=True, exist_ok=True)
    with ReachyMini(media_backend="default") as mini:
        for index, person in enumerate(args.people):
            if index:
                say(f"Merci. Au suivant, {person}, mets-toi devant le robot.")
                time.sleep(args.pause)
            say(f"{person}, mets-toi devant le robot, tout seul. On commence dans cinq secondes.")
            time.sleep(5)
            for pose, instruction in POSES:
                say(instruction)
                time.sleep(1.5)
                frame = fresh_frame(mini)
                if frame is not None:
                    cv2.imwrite(str(out_dir / f"{person}_{pose}.jpg"), frame)
                beep()
                time.sleep(1)
        say("C'est terminé, merci !")


if __name__ == "__main__":
    main()
