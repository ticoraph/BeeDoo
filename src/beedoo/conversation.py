"""Conversation : BeeDoo n'écoute que lorsqu'il voit une personne connue (option 1, voir DECISIONS.md).

Cycle : une personne connue est devant lui -> le micro s'allume -> chaque phrase complète est
transcrite, envoyée au LLM, et la réponse est dite à voix haute -> quand plus aucun visage n'est vu
pendant `ABSENCE` secondes, la conversation se termine : micro coupé, historique oublié.
Sans personne connue en vue, ou en mode muet, le micro n'est pas lu du tout.

Aucun contenu (phrase entendue, réponse) dans les logs : seulement des durées.
"""

import logging
import threading
import time
from collections.abc import Callable

from beedoo.llm.chat import NE_SAIT_PAS, LLMError
from beedoo.miniapps.base import Contexte, Reponse
from beedoo.runtime import Runtime
from beedoo.state import State
from beedoo.voice.segmenter import Utterance, UtteranceSegmenter
from beedoo.voice.stt import STTError, plausible

log = logging.getLogger(__name__)

ABSENCE = 30.0        # secondes sans voir de visage avant de finir la conversation
FRAICHEUR = 6.0       # âge maximal (s) d'une analyse de la caméra pour la croire encore valable
VISAGE_VU = {"reconnu", "inconnu", "ambigu", "trop_petit"}  # états où un visage est devant le robot
LECTURE = 0.05        # durée (s) maximale d'une lecture du micro
PAUSE_PARTIES = 0.8   # secondes entre deux parties d'une réponse (mise en place, puis chute d'une blague)


class Conversation:
    def __init__(self, runtime: Runtime, media, transcribe: Callable, chat,
                 clock: Callable[[], float] = time.monotonic, routeur=None) -> None:
        self._runtime = runtime
        self._media = media
        self._transcribe = transcribe  # (audio, samplerate) -> texte
        self._chat = chat
        self._routeur = routeur  # mini-applications : essayées avant le LLM
        self._clock = clock
        self._segmenteur: UtteranceSegmenter | None = None
        self._enregistre = False
        self._dernier_vu = float("-inf")
        self._personne: str | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="beedoo-conversation", daemon=True)

    # --- cycle de vie -------------------------------------------------------------------------
    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)
        self._couper_micro()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as erreur:
                log.warning("conversation : erreur (%s)", type(erreur).__name__)
                log.debug("détail", exc_info=True)
                self._stop.wait(1.0)

    # --- une itération ------------------------------------------------------------------------
    def tick(self) -> None:
        runtime = self._runtime
        connu = self._observer()
        if runtime.settings.muet:
            self._terminer()
            self._stop.wait(0.2)
            return
        etat = runtime.machine.state
        if etat == State.VEILLE:
            if self._enregistre:
                self._couper_micro()
            if connu and not (runtime.speaker and runtime.speaker.parle):
                self._demarrer()
            else:
                self._stop.wait(0.2)
        elif etat == State.ECOUTE:
            if self._clock() - self._dernier_vu > ABSENCE:
                self._terminer()
                return
            phrase = self._ecouter()
            if phrase is not None:
                self._tour(phrase)
        else:  # réflexion ou parole décidées ailleurs (salutation) : on n'écoute pas
            self._vider()
            self._stop.wait(0.05)

    # --- présence -----------------------------------------------------------------------------
    def _observer(self) -> bool:
        """Met à jour ce que la caméra voit. Renvoie True si une personne connue est devant le robot."""
        vision = self._runtime.vision
        if vision is None:
            return False
        lecture = vision.status()
        if lecture["age"] > FRAICHEUR:
            return False
        if lecture["statut"] in VISAGE_VU:
            self._dernier_vu = self._clock()
        if lecture["statut"] == "reconnu":
            self._personne = lecture["personne"]
            return True
        return False

    def _prenom(self) -> str:
        faces = self._runtime.faces
        if self._personne and faces is not None:
            return faces.display_name(self._personne)
        return "inconnu"

    # --- micro --------------------------------------------------------------------------------
    def _demarrer(self) -> None:
        self._media.start_recording()
        self._enregistre = True
        self._segmenteur = UtteranceSegmenter(self._media.get_input_audio_samplerate())
        self._vider()
        self._aller(State.ECOUTE)
        log.info("conversation : le micro est allumé")

    def _couper_micro(self) -> None:
        if self._enregistre:
            try:
                self._media.stop_recording()
            finally:
                self._enregistre = False

    def _terminer(self) -> None:
        self._couper_micro()
        self._chat.reset()
        if self._routeur is not None:
            self._routeur.reset()
        self._runtime.echange = None  # ce qui s'est dit ne survit pas à la conversation
        if self._runtime.machine.state == State.ECOUTE:
            self._aller(State.VEILLE)
            log.info("conversation : terminée, le micro est coupé")

    def _lire(self) -> list:
        morceaux = []
        fin = time.monotonic() + LECTURE
        while time.monotonic() < fin:
            echantillon = self._media.get_audio_sample()
            if echantillon is None:
                break
            morceaux.append(echantillon.mean(axis=1) if echantillon.ndim == 2 else echantillon)
        return morceaux

    def _vider(self) -> None:
        """Jette l'audio en attente (pendant que BeeDoo parle ou réfléchit, rien ne doit s'accumuler)."""
        if self._enregistre:
            self._lire()
            self._segmenteur = UtteranceSegmenter(self._segmenteur.samplerate) if self._segmenteur else None

    def _ecouter(self) -> Utterance | None:
        doa = self._media.get_DoA()
        parole = bool(doa and doa[1])
        for morceau in self._lire():
            phrase = self._segmenteur.feed(morceau, parole)
            if phrase is not None:
                return phrase
        return None

    # --- un tour de parole ----------------------------------------------------------------------
    def _aller(self, etat: State) -> None:
        try:
            self._runtime.machine.go(etat)
        except ValueError:
            log.debug("transition ignorée vers %s", etat.value)

    def _miniapp(self, texte: str) -> Reponse | None:
        """Réponse d'une mini-application si la phrase en déclenche une ; elle est ajoutée à l'historique du LLM."""
        if self._routeur is None:
            return None
        reponse = self._routeur.router(texte, Contexte(settings=self._runtime.settings, prenom=self._prenom()))
        if reponse is not None:
            self._chat.memoriser(texte, " ".join(reponse.parties))
        return reponse

    def _dire(self, reponse: Reponse) -> None:
        """Dit les parties l'une après l'autre ; le geste accompagne la dernière."""
        runtime = self._runtime
        for i, partie in enumerate(reponse.parties):
            derniere = i == len(reponse.parties) - 1
            if derniere and reponse.geste and runtime.gestes is not None:
                runtime.gestes.play(reponse.geste)
            if runtime.speaker is not None:
                runtime.speaker.say(partie)
            if not derniere:
                self._stop.wait(PAUSE_PARTIES)

    def _tour(self, phrase: Utterance) -> None:
        runtime = self._runtime
        self._aller(State.REFLEXION)
        debut = time.monotonic()
        try:
            texte = self._transcribe(phrase.audio, phrase.samplerate)
        except STTError as erreur:
            log.warning("conversation : transcription impossible (%s)", erreur)
            texte = ""
        if not plausible(texte):
            log.info("conversation : phrase de %.1f s ignorée (non comprise)", phrase.duration)
            self._aller(State.ECOUTE)
            return
        transcription = time.monotonic() - debut
        runtime.echange = {"entendu": texte, "dit": ""}
        reponse = self._miniapp(texte)
        if reponse is None:
            try:
                reponse = Reponse((self._chat.reply(texte, self._prenom()),))
            except LLMError as erreur:
                log.warning("conversation : le LLM n'a pas répondu (%s)", erreur)
                reponse = Reponse((NE_SAIT_PAS,))
        reflexion = time.monotonic() - debut - transcription
        dit = " ".join(reponse.parties)
        runtime.echange = {"entendu": texte, "dit": dit}
        self._aller(State.PAROLE)
        self._dire(reponse)
        log.info("conversation : phrase de %.1f s, transcription %.1f s, réponse %.1f s",
                 phrase.duration, transcription, reflexion)
        self._aller(State.ECOUTE)
        self._vider()
