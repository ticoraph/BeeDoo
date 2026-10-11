"""Enregistre quelques secondes au micro du Reachy Mini, puis rejoue le son.

Lancer :
    python scripts/record_playback.py
    python scripts/record_playback.py --duration 3
"""

import argparse
import tempfile
import time
from pathlib import Path

import numpy as np

from reachy_mini import ReachyMini
from reachy_mini.media.audio_utils import save_audio_to_wav
from reachy_mini.media.gstreamer_utils import audio_duration_seconds

TIMEOUT = 1  # secondes d'attente max pour que le micro soit prêt


def record(mini: "ReachyMini", duration: float, output_file: Path) -> bool:
    """Enregistre `duration` secondes et sauvegarde dans output_file. Retourne True si ok."""
    audio_samples = []
    mini.media.start_recording()

    print("En attente du micro...")
    start_time = time.time()
    while mini.media.get_audio_sample() is None and time.time() - start_time < TIMEOUT:
        time.sleep(0.005)

    if time.time() - start_time >= TIMEOUT:
        print(f"Timeout : le micro n'a pas répondu en {TIMEOUT}s.")
        mini.media.stop_recording()
        return False

    print(f"🎙️  Enregistrement pendant {duration}s...")
    start_time = time.time()
    while time.time() - start_time < duration:
        sample = mini.media.get_audio_sample()
        if sample is not None:
            audio_samples.append(sample)

    mini.media.stop_recording()

    if not audio_samples:
        print("Aucun son enregistré.")
        return False

    audio_data = np.concatenate(audio_samples, axis=0)
    samplerate = mini.media.get_input_audio_samplerate()
    save_audio_to_wav(audio_data, samplerate, str(output_file))
    return True


def playback(mini: "ReachyMini", audio_file: Path) -> None:
    """Rejoue le fichier audio enregistré."""
    print("🔊  Lecture...")
    mini.media.play_sound(str(audio_file))
    time.sleep(audio_duration_seconds(str(audio_file)))
    print("Terminé.")


def main(duration: float, backend: str) -> None:
    with ReachyMini(log_level="INFO", media_backend=backend) as mini:
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_file = Path(tmp_dir) / "recorded_audio.wav"
            if record(mini, duration, audio_file):
                playback(mini, audio_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enregistre quelques secondes au micro puis rejoue le son."
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Durée de l'enregistrement en secondes (défaut : 5).",
    )
    parser.add_argument(
        "--backend",
        type=str,
        choices=["default", "local", "webrtc"],
        default="default",
        help="Backend média à utiliser.",
    )

    args = parser.parse_args()
    main(duration=args.duration, backend=args.backend)
