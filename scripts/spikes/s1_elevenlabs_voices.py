"""Essai S1 (abandonné, voir DECISIONS.md D1) : chercher une voix d'enfant française dans la Voice Library ElevenLabs.

Lancer :
    python scripts/spikes/s1_elevenlabs_voices.py
    python scripts/spikes/s1_elevenlabs_voices.py --search enfant --age young

Affiche les voix trouvées (nom, âge, accent, description, identifiant). Aucune clé n'est affichée.
"""

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

import certifi

from beedoo.config import Config

API = "https://api.elevenlabs.io/v1"
# Le Python de python.org sur macOS n'a pas les certificats racine : on utilise ceux de certifi.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def get(path: str, key: str, **params) -> dict:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
    request = urllib.request.Request(f"{API}{path}?{query}", headers={"xi-api-key": key})
    with urllib.request.urlopen(request, timeout=20, context=SSL_CONTEXT) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--search", default="")
    parser.add_argument("--age", default="", help="young, middle_aged, old")
    parser.add_argument("--language", default="fr")
    parser.add_argument("--size", type=int, default=30)
    args = parser.parse_args()

    Config.load()  # charge .env
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        print("ELEVENLABS_API_KEY manquante dans .env")
        return 1

    try:
        data = get("/shared-voices", key, language=args.language, search=args.search,
                   age=args.age, page_size=args.size)
    except urllib.error.HTTPError as error:
        print(f"Erreur HTTP {error.code} : {error.read().decode()[:300]}")
        return 1

    voices = data.get("voices", [])
    print(f"{len(voices)} voix (recherche={args.search!r}, âge={args.age!r}, langue={args.language})")
    for v in voices:
        print(f"- {v.get('name')} | âge={v.get('age')} | genre={v.get('gender')} | accent={v.get('accent')} "
              f"| usage={v.get('use_case')} | id={v.get('voice_id')}\n    {(v.get('description') or '')[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
