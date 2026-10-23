"""Point d'entrée de l'application BeeDoo pour le SDK Reachy Mini.

BeeDoo charge sa configuration et ses réglages, se met en position neutre, puis reste en veille
jusqu'à l'arrêt. L'écoute, la parole et les gestes arrivent phase par phase.
"""

import logging
import threading

from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.utils import create_head_pose

from beedoo.config import Config
from beedoo.logs import setup_logging
from beedoo.settings import Settings
from beedoo.runtime import Runtime
from beedoo.ui.web import WebServer

log = logging.getLogger(__name__)


class Beedoo(ReachyMiniApp):
    # L'interface web est lancée dans run() (ui/web.py) : on n'utilise pas le serveur du SDK.
    custom_app_url: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        setup_logging()
        config = Config.load()
        settings = Settings.load(config.data_dir)
        runtime = Runtime(config=config, settings=settings)
        log.info("BeeDoo démarre (muet=%s, clé OpenAI %s)", settings.muet,
                 "absente" if config.missing_keys() else "présente")

        web = WebServer(runtime, config.web_port)
        try:
            web.start()
        except OSError:
            log.warning("interface web indisponible (port %d occupé ?)", config.web_port)

        reachy_mini.goto_target(create_head_pose(), antennas=[0.0, 0.0], duration=1.0)
        try:
            stop_event.wait()
        finally:
            web.stop()
            log.info("BeeDoo s'arrête (état : %s)", runtime.machine.state.value)


if __name__ == "__main__":
    app = Beedoo()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
