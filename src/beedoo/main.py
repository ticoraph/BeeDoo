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
from beedoo.state import StateMachine

log = logging.getLogger(__name__)


class Beedoo(ReachyMiniApp):
    # Pas d'interface web pour l'instant (Gradio, prévu en phase 2).
    custom_app_url: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        setup_logging()
        config = Config.load()
        settings = Settings.load(config.data_dir)
        machine = StateMachine()
        log.info("BeeDoo démarre (muet=%s, clé OpenAI %s)", settings.muet,
                 "absente" if config.missing_keys() else "présente")

        reachy_mini.goto_target(create_head_pose(), antennas=[0.0, 0.0], duration=1.0)
        stop_event.wait()
        log.info("BeeDoo s'arrête (état : %s)", machine.state.value)


if __name__ == "__main__":
    app = Beedoo()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
