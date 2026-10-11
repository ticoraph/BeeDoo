"""Essai S3 : enrôler une personne avec plusieurs poses, puis la reconnaître (une pose mise de côté).

    python scripts/spikes/s3_enroll_demo.py data/spikes/labeled personne1 [--model ArcFace] [--save]

Test « un contre le reste » : pour chaque image, on enrôle les autres puis on identifie celle-là.
Avec --save, on enrôle ensuite toutes les images dans data/personnes/<personne>/ (ignoré par git).
Nécessite deepface (voir DECISIONS.md : installation à part).
"""

import argparse
import tempfile
from pathlib import Path

from beedoo.config import Config
from beedoo.vision.faces import DEFAULT_DETECTOR, FaceRecognizer, FaceStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folder")
    parser.add_argument("person")
    parser.add_argument("--model", default="ArcFace")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    images = sorted(Path(args.folder).glob(f"{args.person}_*.jpg"))
    print(f"{len(images)} images de {args.person}, modèle {args.model}, détecteur {DEFAULT_DETECTOR}")
    recognized = 0
    for held_out in images:
        with tempfile.TemporaryDirectory() as tmp:
            recognizer = FaceRecognizer(FaceStore(Path(tmp), model=args.model))
            added = recognizer.enroll(args.person, [str(i) for i in images if i != held_out])
            match = recognizer.identify(str(held_out))
        ok = match.person == args.person
        recognized += ok
        distance = "-" if match.distance is None else f"{match.distance:.2f}"
        print(f"  {held_out.stem.split('_', 1)[1]:7s} ({added} empreintes) -> "
              f"{'reconnue' if ok else 'NON reconnue':13s} distance={distance} {match.reason}")
    print(f"{recognized}/{len(images)} reconnues (seuil {FaceRecognizer(FaceStore(Path('.'), args.model)).threshold})")

    if args.save:
        store = FaceStore(Config.load().data_dir, model=args.model)
        count = FaceRecognizer(store).enroll(args.person, [str(i) for i in images])
        print(f"{count} empreintes enregistrées dans {store.root / args.person}")


if __name__ == "__main__":
    main()
