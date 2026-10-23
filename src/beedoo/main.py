"""Point d'entrée de l'application BeeDoo pour le SDK Reachy Mini.

BeeDoo charge sa configuration et ses réglages, se met en position neutre, puis reste en veille
jusqu'à l'arrêt. Il regarde la caméra et salue les personnes qu'il reconnaît. L'écoute et la
conversation arrivent phase par phase.
"""

import logging
import threading

from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.utils import create_head_pose

from beedoo.config import Config
from beedoo.gestures.player import GesturePlayer
from beedoo.logs import setup_logging
from beedoo.greeting import Salutation
from beedoo.runtime import Runtime
from beedoo.settings import Settings
from beedoo.ui.web import WebServer
from beedoo.vision.enrollment import Enrollment
from beedoo.vision.faces import FaceRecognizer, FaceStore
from beedoo.vision.greeter import Greeter
from beedoo.vision.loop import VisionLoop
from beedoo.voice.speaker import Speaker

log = logging.getLogger(__name__)


class Beedoo(ReachyMiniApp):
    # L'interface web est lancée dans run() (ui/web.py) : on n'utilise pas le serveur du SDK.
    custom_app_url: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        setup_logging()
        config = Config.load()
        settings = Settings.load(config.data_dir)
        faces = FaceStore(config.data_dir)
        recognizer = FaceRecognizer(faces)

        def get_frame():
            return reachy_mini.media.get_frame()

        runtime = Runtime(config=config, settings=settings, gestes=GesturePlayer(reachy_mini),
                          speaker=Speaker(reachy_mini, config, settings), faces=faces, greeter=Greeter(),
                          enrolement=Enrollment(get_frame, recognizer))
        vision = VisionLoop(get_frame, recognizer.identify, runtime.greeter, Salutation(runtime).on_event,
                            active=lambda: not runtime.enrolement.en_cours)
        runtime.vision = vision
        log.info("BeeDoo démarre (muet=%s, clé OpenAI %s)", settings.muet,
                 "absente" if config.missing_keys() else "présente")

        web = WebServer(runtime, config.web_port)
        try:
            web.start()
        except OSError:
            log.warning("interface web indisponible (port %d occupé ?)", config.web_port)

        reachy_mini.goto_target(create_head_pose(), antennas=[0.0, 0.0], duration=1.0)
        vision.start()
        try:
            stop_event.wait()
        finally:
            vision.stop()
            web.stop()
            runtime.speaker.stop()
            runtime.gestes.stop()
            log.info("BeeDoo s'arrête (état : %s)", runtime.machine.state.value)


if __name__ == "__main__":
    app = Beedoo()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
