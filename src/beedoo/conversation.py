"""Conversation : BeeDoo n'écoute que lorsqu'il voit une personne connue (option 1, voir DECISIONS.md).

Cycle : une personne connue est devant lui -> le micro s'allume -> chaque phrase complète est
transcrite, envoyée au LLM, et la réponse est dite à voix haute -> quand plus aucun visage n'est vu
pendant `ABSENCE` secondes, la conversation se termine : micro coupé, historique oublié.
Sans personne connue en vue, ou en mode muet, le micro n'est pas lu du tout.

Mémoire (phase 8) : seulement pour les personnes qui ont donné leur consentement. Les souvenirs d'UNE
personne ne servent qu'à elle : si la personne reconnue change, ou si seul un inconnu est vu depuis plus
de `RECONNU_RECEMMENT` secondes, l'historique est remis à zéro. La conversation est écrite sur le disque après chaque échange ; les faits
retenus sont mis à jour, en arrière-plan, après `PAUSE_EXTRACTION` secondes de silence, puis à la fin de la
conversation ou à l'arrêt.

Aucun contenu (phrase entendue, réponse, fait) dans les logs : seulement des durées et des comptes.
"""

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime

from beedoo.llm.chat import NE_SAIT_PAS, LLMError
from beedoo.memory import extraction
from beedoo.memory.store import RIEN
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
RECONNU_RECEMMENT = 10.0  # s : au-delà, on ne sait plus à qui on parle, donc on n'utilise aucun souvenir
PAUSE_EXTRACTION = 20.0  # s de silence après un échange avant de retenir des faits (sans attendre la fin)
ATTENTE_ARRET = 20.0  # s : temps laissé à l'enregistrement de la conversation quand l'application s'arrête
PAUSE_PARTIES = 0.8   # secondes entre deux parties d'une réponse (mise en place, puis chute d'une blague)


class Conversation:
    def __init__(self, runtime: Runtime, media, transcribe: Callable, chat,
                 clock: Callable[[], float] = time.monotonic, routeur=None,
                 maintenant: Callable[[], datetime] = datetime.now) -> None:
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
        self._reconnu_a = float("-inf")   # dernière fois où une personne connue a été reconnue
        self._maintenant = maintenant
        self._pid_conv: str | None = None  # personne à qui l'on parle dans la conversation en cours
        self._tours: list[tuple[str, str]] = []  # (ce qu'elle a dit, ce que BeeDoo a répondu), si elle a consenti
        self._a_extraire: list[tuple[str, str]] = []  # échanges pas encore passés au crible pour en retenir des faits
        self._chemin_conv = None                      # fichier de la conversation en cours
        self._dernier_tour = float("-inf")
        self._dernier_resultat: dict | None = None
        self._debut_conv = maintenant()
        self._verrou_extraction = threading.Lock()   # une extraction à la fois
        self._consolidations: list[threading.Thread] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="beedoo-conversation", daemon=True)

    # --- cycle de vie -------------------------------------------------------------------------
    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=10)
        self._couper_micro()
        self._clore_conversation()
        for fil in self._consolidations:  # laisse finir l'enregistrement de ce qui vient d'être dit
            fil.join(timeout=ATTENTE_ARRET)

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
            self._extraire_si_calme()
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
            self._reconnu_a = self._clock()
            return True
        return False

    def _pid_courant(self) -> str | None:
        """La personne à qui BeeDoo parle, si on l'a reconnue il y a peu ; sinon personne (aucun souvenir utilisé)."""
        if self._personne and self._clock() - self._reconnu_a <= RECONNU_RECEMMENT:
            return self._personne
        return None

    def _prenom(self, pid: str | None = None) -> str:
        faces = self._runtime.faces
        if pid and faces is not None:
            return faces.display_name(pid)
        return "inconnu"

    # --- mémoire ------------------------------------------------------------------------------
    def _memoire(self):
        return self._runtime.memoire

    def _a_consenti(self, pid: str | None) -> bool:
        memoire = self._memoire()
        return bool(pid and memoire is not None and memoire.consentement(pid))

    def _changer_de_personne(self, pid: str | None) -> None:
        """Quand la personne change, on enregistre ce qui précède et on repart d'une page blanche."""
        if pid == self._pid_conv:
            return
        self._clore_conversation()
        self._chat.reset()
        if self._routeur is not None:
            self._routeur.reset()
        self._pid_conv = pid

    def _noter_echange(self, pid: str, texte: str, dit: str) -> None:
        """Garde l'échange et écrit tout de suite la conversation sur le disque (l'utilisateur peut la relire)."""
        self._tours.append((texte, dit))
        self._a_extraire.append((texte, dit))
        self._dernier_tour = self._clock()
        try:
            nom = self._runtime.faces.display_name(pid) if self._runtime.faces is not None else pid
            self._chemin_conv = self._memoire().enregistrer_conversation(
                pid, nom, self._tours, self._debut_conv, self._chemin_conv)
        except OSError as erreur:
            log.warning("mémoire : conversation non écrite (%s)", type(erreur).__name__)

    def _extraire_si_calme(self) -> None:
        """Après un moment de silence, retient des faits de ce qui vient d'être dit (sans attendre la fin)."""
        if (self._a_extraire and self._pid_conv and self._clock() - self._dernier_tour >= PAUSE_EXTRACTION
                and not any(f.is_alive() for f in self._consolidations)):
            self._lancer_extraction()

    def _lancer_extraction(self) -> None:
        pid, tours = self._pid_conv, self._a_extraire
        self._a_extraire = []
        if not pid or not tours or self._memoire() is None:
            return
        fil = threading.Thread(target=self._extraire, args=(pid, tours), name="beedoo-memoire", daemon=True)
        self._consolidations = [f for f in self._consolidations if f.is_alive()] + [fil]
        fil.start()

    def _clore_conversation(self) -> None:
        """Fin de conversation : retient les faits de ce qui reste, puis repart d'une conversation vierge."""
        self._lancer_extraction()
        self._tours = []
        self._chemin_conv = None
        self._debut_conv = self._maintenant()

    def _extraire(self, pid: str, tours: list[tuple[str, str]]) -> None:
        runtime, memoire = self._runtime, self._runtime.memoire
        with self._verrou_extraction:
            try:
                if memoire.consentement(pid):  # peut avoir été retiré depuis
                    resultat = extraction.mettre_a_jour(runtime.config, memoire, pid, tours)
                    self._dernier_resultat = {"ajoutes": resultat.ajoutes, "retires": resultat.retires,
                                              "rejetes": resultat.rejetes}
            except (LLMError, OSError, ValueError) as erreur:
                log.warning("mémoire : faits non retenus (%s)", type(erreur).__name__)
            except Exception as erreur:
                log.warning("mémoire : erreur inattendue (%s)", type(erreur).__name__)
                log.debug("détail", exc_info=True)

    def info_memoire(self) -> dict:
        """Où en est la mémoire, pour la page : jamais de contenu, seulement des comptes."""
        pid = self._pid_courant()
        if not self._a_consenti(pid):
            return {"etat": "desactivee" if pid else "personne"}
        if any(f.is_alive() for f in self._consolidations):
            etat = "extraction"
        elif self._tours:
            etat = "enregistre"
        else:
            etat = "attente"
        return {"etat": etat, "phrases": len(self._tours), "en_attente": len(self._a_extraire),
                "dernier": self._dernier_resultat, "pause": PAUSE_EXTRACTION}

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
        self._clore_conversation()
        self._pid_conv = None
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

    def _miniapp(self, texte: str, pid: str | None) -> Reponse | None:
        """Réponse d'une mini-application si la phrase en déclenche une ; elle est ajoutée à l'historique du LLM."""
        if self._routeur is None:
            return None
        reponse = self._routeur.router(texte, Contexte(settings=self._runtime.settings, prenom=self._prenom(pid)))
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
        pid = self._pid_courant()
        self._changer_de_personne(pid)
        memoire = self._memoire()
        souvenirs = memoire.souvenirs(pid) if memoire is not None else RIEN
        reponse = self._miniapp(texte, pid)
        if reponse is None:
            try:
                reponse = Reponse((self._chat.reply(texte, self._prenom(pid), souvenirs),))
            except LLMError as erreur:
                log.warning("conversation : le LLM n'a pas répondu (%s)", erreur)
                reponse = Reponse((NE_SAIT_PAS,))
        reflexion = time.monotonic() - debut - transcription
        dit = " ".join(reponse.parties)
        runtime.echange = {"entendu": texte, "dit": dit}
        self._aller(State.PAROLE)
        if self._a_consenti(pid):
            self._noter_echange(pid, texte, dit)
        self._dire(reponse)
        log.info("conversation : phrase de %.1f s, transcription %.1f s, réponse %.1f s",
                 phrase.duration, transcription, reflexion)
        self._aller(State.ECOUTE)
        self._vider()
