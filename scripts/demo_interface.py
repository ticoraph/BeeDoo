"""Lance l'interface web de BeeDoo avec des données entièrement FICTIVES, sans robot ni clé API.

    python scripts/demo_interface.py [--port 8799] [--duree 600]

Sert à regarder l'interface, développer la page ou faire des captures d'écran pour la documentation.
Les personnes, souvenirs et conversations ci-dessous sont inventés ; rien n'est lu ni écrit dans `data/`
(un dossier temporaire est utilisé et supprimé à la fin). Aucune requête n'est envoyée sur Internet.
"""

import argparse
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

from beedoo import logs, robot_volume
from beedoo.config import Config
from beedoo.gestures.library import GESTES
from beedoo.memory.store import MemoryStore
from beedoo.miniapps import toutes
from beedoo.runtime import Runtime
from beedoo.settings import Settings
from beedoo.ui.web import WebServer
from beedoo.vision.faces import FaceStore
from beedoo.vision.greeter import Greeter


class FauxGestes:
    occupe = False

    def play(self, nom):
        return nom in GESTES


class FausseVoix:
    parle = False

    def say(self, texte):
        return True


class FausseVision:
    def status(self):
        return {"statut": "reconnu", "taille": 188, "personne": "mamie-jeanne", "age": 0.4}


class FausseConversation:
    def info_memoire(self):
        return {"etat": "enregistre", "phrases": 3, "en_attente": 1, "pause": 20,
                "dernier": {"ajoutes": 2, "retires": 0, "rejetes": 0}}


class FauxEnrolement:
    en_cours = False

    def status(self):
        return {"etat": "libre", "ajoutes": 0, "total": 6, "essais": 0, "pose": None, "consigne": None,
                "derniere": None, "taille": None, "min_taille": 60}

    def start(self, nom, apres=None):
        return False


def monter(data_dir: Path) -> Runtime:
    os.environ["BEEDOO_DATA_DIR"] = str(data_dir)
    config = Config.load(env_file=data_dir / "absent.env")
    settings = Settings(ville="Paris")
    runtime = Runtime(config=config, settings=settings, miniapps=toutes())

    faces = FaceStore(data_dir)
    faces.add("Mamie Jeanne", [[1.0, 0.0, 0.0]])
    faces.add("Léa", [[0.0, 1.0, 0.0]])
    memoire = MemoryStore(data_dir)
    memoire.set_consentement("mamie-jeanne", True)
    memoire.ecrire_faits("mamie-jeanne", ["Sa petite-fille s'appelle Léa.", "Elle aime les chats.",
                                          "Son chat s'appelle Pompon.", "Elle fait des gâteaux au chocolat."])
    memoire.enregistrer_conversation("mamie-jeanne", "Mamie Jeanne", [("Bonjour BeeDoo", "Coucou Mamie Jeanne !")],
                                     datetime(2026, 10, 22, 15, 30))
    runtime.faces, runtime.memoire, runtime.greeter = faces, memoire, Greeter()
    runtime.gestes, runtime.speaker, runtime.vision = FauxGestes(), FausseVoix(), FausseVision()
    runtime.conversation, runtime.enrolement = FausseConversation(), FauxEnrolement()
    runtime.echange = {"entendu": "Bonjour BeeDoo, tu peux me raconter une blague ?",
                       "dit": "Ah, une blague de Toto ! Écoute bien. Pourquoi Toto emmène-t-il une échelle à l'école ? "
                              "Pour aller à l'école supérieure !"}
    return runtime


def journal_fictif() -> None:
    logs.JOURNAL.setFormatter(logging.Formatter(logs.FORMAT))
    exemples = [
        ("beedoo.main", logging.INFO, "BeeDoo démarre (muet=False, clé OpenAI présente)"),
        ("beedoo.ui.web", logging.INFO, "interface web : http://127.0.0.1:8765"),
        ("beedoo.vision.loop", logging.INFO, "vision : trop_petit (52 px)"),
        ("beedoo.vision.loop", logging.INFO, "vision : reconnu (188 px)"),
        ("beedoo.greeting", logging.INFO, "personne reconnue, salutation"),
        ("beedoo.conversation", logging.INFO, "conversation : le micro est allumé"),
        ("beedoo.state", logging.INFO, "état : veille -> écoute"),
        ("beedoo.miniapps.routeur", logging.INFO, "mini-application : toto"),
        ("beedoo.conversation", logging.INFO, "conversation : phrase de 3.2 s, transcription 1.1 s, réponse 0.0 s"),
        ("beedoo.memory.extraction", logging.INFO, "mémoire : 2 ajoutés, 0 retirés, 0 rejetés"),
        ("beedoo.robot_volume", logging.WARNING, "volume : le daemon ne répond pas (URLError)"),
    ]
    for nom, niveau, message in exemples:
        logs.JOURNAL.handle(logging.LogRecord(nom, niveau, __file__, 1, message, None, None))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--duree", type=float, default=600, help="secondes avant l'arrêt")
    args = parser.parse_args()

    volume = {"valeur": 70}  # volume du robot simulé : rien n'est envoyé à un vrai daemon
    robot_volume.lire = lambda url: volume["valeur"]
    robot_volume.regler = lambda url, v: volume.update(valeur=v) or True

    with tempfile.TemporaryDirectory() as dossier:
        runtime = monter(Path(dossier))
        journal_fictif()
        serveur = WebServer(runtime, args.port)
        serveur.start()
        print(f"Interface de démonstration : http://127.0.0.1:{args.port}  (arrêt dans {args.duree:.0f} s, Ctrl+C pour sortir)")
        try:
            time.sleep(args.duree)
        except KeyboardInterrupt:
            pass
        finally:
            serveur.stop()


if __name__ == "__main__":
    main()
