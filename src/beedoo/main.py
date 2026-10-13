"""Point d'entrée de l'application BeeDoo pour le SDK Reachy Mini.

Squelette : BeeDoo se met en position neutre et attend l'arrêt. Les fonctions
arrivent phase par phase.
"""

import threading

from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.utils import create_head_pose


class Beedoo(ReachyMiniApp):
    # Pas d'interface web pour l'instant (Gradio, prévu en phase 2).
    custom_app_url: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        reachy_mini.goto_target(create_head_pose(), antennas=[0.0, 0.0], duration=1.0)
        stop_event.wait()


if __name__ == "__main__":
    app = Beedoo()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
