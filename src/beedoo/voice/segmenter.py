"""Découpe le flux du micro en phrases à partir d'un indicateur « parole détectée ».

L'indicateur vient du micro du robot (ReSpeaker, `get_DoA()`). Ce module ne dépend ni du robot
ni du réseau : il reçoit des morceaux d'audio et dit quand une phrase est terminée.
Seules les phrases complètes partent ensuite vers la reconnaissance vocale (coût et vie privée :
le silence et les bruits ambiants ne sont jamais envoyés).

Le temps est compté en échantillons, pas à l'horloge : le résultat ne dépend pas de la vitesse du robot.
"""

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Utterance:
    audio: np.ndarray  # échantillons, forme (n,) ou (n, canaux)
    samplerate: int

    @property
    def duration(self) -> float:
        return len(self.audio) / self.samplerate


class UtteranceSegmenter:
    def __init__(self, samplerate: int, preroll: float = 0.4, hangover: float = 0.9,
                 min_speech: float = 0.3, max_duration: float = 20.0):
        """
        preroll      : secondes gardées avant le début de la parole (pour ne pas couper le premier mot)
        hangover     : silence (en secondes) qui termine une phrase
        min_speech   : en dessous, la « phrase » est un bruit et on la jette
        max_duration : au-delà, on coupe de force pour ne pas accumuler
        """
        self.samplerate = samplerate
        # Tout est compté en échantillons entiers : pas d'erreur d'arrondi sur les secondes.
        self._preroll = round(preroll * samplerate)
        self._hangover = round(hangover * samplerate)
        self._min_speech = round(min_speech * samplerate)
        self._max = round(max_duration * samplerate)
        self._preroll_chunks: deque[np.ndarray] = deque()
        self._reset()

    def _reset(self) -> None:
        self._chunks: list[np.ndarray] = []
        self._speaking = False
        self._speech = 0     # échantillons de parole
        self._silence = 0    # échantillons de silence consécutifs
        self._total = 0

    def feed(self, chunk: np.ndarray, is_speech: bool) -> Utterance | None:
        """Ajoute un morceau d'audio. Retourne la phrase quand elle vient de se terminer."""
        size = len(chunk)
        if not self._speaking:
            if not is_speech:
                self._preroll_chunks.append(chunk)
                while sum(len(c) for c in self._preroll_chunks) > self._preroll and len(self._preroll_chunks) > 1:
                    self._preroll_chunks.popleft()
                return None
            self._speaking = True
            self._chunks = list(self._preroll_chunks)
            self._total = sum(len(c) for c in self._chunks)
            self._preroll_chunks.clear()

        self._chunks.append(chunk)
        self._total += size
        if is_speech:
            self._speech += size
            self._silence = 0
        else:
            self._silence += size

        if self._silence >= self._hangover or self._total >= self._max:
            return self._finish()
        return None

    def _finish(self) -> Utterance | None:
        audio = np.concatenate(self._chunks) if self._chunks else None
        long_enough = self._speech >= self._min_speech
        self._reset()
        return Utterance(audio, self.samplerate) if long_enough and audio is not None else None
