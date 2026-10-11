"""Essai S4 : écoute permanente avec la détection de voix du micro du robot.

    python scripts/spikes/s4_listen.py listen --duration 40   # vous parlez par phrases, avec des pauses
    python scripts/spikes/s4_listen.py echo                   # le robot parle seul : s'entend-il lui-même ?

`listen` découpe le flux en phrases (UtteranceSegmenter) et enregistre chacune dans
data/spikes/utterances/ (ignoré par git : ce sont des voix). Rien n'est envoyé sur le réseau.
`echo` joue la voix de BeeDoo (data/spikes/fable_bidou.mp3) et mesure ce que le micro entend pendant ce temps.
"""

import argparse
import subprocess
import time
import wave
from pathlib import Path

import numpy as np

from beedoo.voice.segmenter import UtteranceSegmenter
from reachy_mini import ReachyMini

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "spikes" / "utterances"


def drain(media, max_seconds: float = 0.05) -> list[np.ndarray]:
    """Morceaux d'audio disponibles (mono), pendant au plus `max_seconds`.

    get_audio_sample() attend jusqu'à 20 ms un morceau, et le micro en fournit un toutes les 10 ms :
    sans limite de temps, cette boucle ne s'arrêterait jamais.
    """
    chunks = []
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        sample = media.get_audio_sample()
        if sample is None:
            break
        chunks.append(sample.mean(axis=1) if sample.ndim == 2 else sample)
    return chunks


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio)))) if len(audio) else 0.0


def beep() -> None:
    subprocess.run(["afplay", "/System/Library/Sounds/Pop.aiff"], check=False)


def save_wav(path: Path, audio: np.ndarray, samplerate: int) -> None:
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(samplerate)
        f.writeframes(pcm.tobytes())


def listen(mini, duration: float) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("utt_*.wav"):
        old.unlink()
    media = mini.media
    rate = media.get_input_audio_samplerate()
    segmenter = UtteranceSegmenter(rate)
    media.start_recording()
    drain(media)
    beep()
    print(f"Écoute pendant {duration:.0f} s (bip = début). Parlez par phrases, avec des pauses.")
    start = time.time()
    count = vad_ticks = ticks = 0
    last_speech = False
    while time.time() - start < duration:
        doa = media.get_DoA()
        speech = bool(doa and doa[1])
        ticks += 1
        vad_ticks += speech
        now = time.time() - start
        if speech != last_speech:
            print(f"  t={now:5.1f}s  voix {'détectée' if speech else 'terminée'}"
                  + (f" (direction {np.degrees(doa[0]):.0f}°)" if speech else ""))
            last_speech = speech
        for chunk in drain(media):
            utterance = segmenter.feed(chunk, speech)
            if utterance:
                count += 1
                save_wav(OUT_DIR / f"utt_{count}.wav", utterance.audio, rate)
                print(f"  >>> phrase {count} : {utterance.duration:.1f} s, niveau {rms(utterance.audio):.3f}")
    media.stop_recording()
    beep()
    print(f"\n{count} phrases détectées | voix détectée {vad_ticks / max(ticks, 1):.0%} du temps "
          f"({ticks} lectures)")


def echo(mini) -> None:
    from reachy_mini.media.gstreamer_utils import audio_duration_seconds

    media = mini.media
    sound = REPO_ROOT / "data" / "spikes" / "fable_bidou.mp3"
    print("durée du son...", flush=True)
    seconds = audio_duration_seconds(str(sound))
    print(f"durée {seconds:.1f} s", flush=True)
    media.start_recording()
    drain(media)

    def measure(label: str, duration: float) -> None:
        levels, vad, ticks = [], 0, 0
        end = time.time() + duration
        while time.time() < end:
            doa = media.get_DoA()
            vad += bool(doa and doa[1])
            ticks += 1
            for chunk in drain(media):
                levels.append(rms(chunk))
        print(f"  {label:34s} niveau moyen {np.mean(levels):.6f} | max {np.max(levels):.6f} | "
              f"voix détectée {vad / max(ticks, 1):.0%}")

    print("Ne parlez pas pendant cet essai. 4 s de silence, puis BeeDoo parle.")
    measure("silence (référence)", 4)
    print("lecture du son...", flush=True)
    media.play_sound(str(sound))
    print("lecture lancée", flush=True)
    measure(f"BeeDoo parle ({seconds:.0f} s)", seconds)
    measure("après (silence)", 3)
    media.stop_recording()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("mode", choices=["listen", "echo"])
    parser.add_argument("--duration", type=float, default=40)
    parser.add_argument("--backend", default="webrtc", choices=["webrtc", "default", "local"],
                        help="webrtc = via le daemon (marche sans permission micro) ; local = micro lu directement")
    args = parser.parse_args()
    with ReachyMini(media_backend=args.backend) as mini:
        listen(mini, args.duration) if args.mode == "listen" else echo(mini)


if __name__ == "__main__":
    main()
