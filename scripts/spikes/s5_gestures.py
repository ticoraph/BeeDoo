"""Essai S5 : gestes simples de BeeDoo (OUI, NON, antennes) avec goto_target().

    python scripts/spikes/s5_gestures.py              # joue tous les gestes
    python scripts/spikes/s5_gestures.py oui non      # seulement ceux-là

Le daemon doit tourner. Aucun changement de couple moteur : seulement goto_target(), jamais moins de 0,5 s
par mouvement. Chaque geste part de la position neutre et y revient.
"""

import sys
import time

import numpy as np

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

NEUTRE = create_head_pose()
ANTENNES_NEUTRES = [0.0, 0.0]


def tete(mini, duree: float, **angles) -> None:
    mini.goto_target(head=create_head_pose(**angles, degrees=True), duration=duree, method="minjerk")


def neutre(mini) -> None:
    mini.goto_target(head=NEUTRE, antennas=ANTENNES_NEUTRES, duration=0.8, method="minjerk")


def oui(mini) -> None:
    for _ in range(2):
        tete(mini, 0.5, pitch=12)
        tete(mini, 0.5, pitch=-8)
    tete(mini, 0.5, pitch=0)


def non(mini) -> None:
    for _ in range(2):
        tete(mini, 0.5, yaw=20)
        tete(mini, 0.5, yaw=-20)
    tete(mini, 0.5, yaw=0)


def antennes_content(mini) -> None:
    haut, bas = np.deg2rad(40), np.deg2rad(-10)
    for _ in range(3):
        mini.goto_target(antennas=[haut, haut], duration=0.5, method="minjerk")
        mini.goto_target(antennas=[bas, bas], duration=0.5, method="minjerk")


def antennes_surprise(mini) -> None:
    ecart = np.deg2rad(60)
    tete(mini, 0.5, pitch=-8)
    mini.goto_target(antennas=[ecart, -ecart], duration=0.5, method="minjerk")
    time.sleep(1.0)


GESTES = {
    "oui": oui,
    "non": non,
    "antennes_content": antennes_content,
    "antennes_surprise": antennes_surprise,
}


def main() -> None:
    noms = sys.argv[1:] or list(GESTES)
    inconnus = [n for n in noms if n not in GESTES]
    if inconnus:
        sys.exit(f"Geste inconnu : {', '.join(inconnus)}. Disponibles : {', '.join(GESTES)}")
    with ReachyMini(media_backend="no_media") as mini:
        neutre(mini)
        for nom in noms:
            print(f"geste : {nom}")
            start = time.time()
            GESTES[nom](mini)
            neutre(mini)
            print(f"  {time.time() - start:.1f} s, retour au neutre")
            time.sleep(0.5)


if __name__ == "__main__":
    main()
