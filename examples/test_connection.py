"""Brief connection + motion smoke test for Reachy Mini Lite.

Requires a running daemon (`reachy-mini-daemon --headless`).
Adapted from reachy_mini/examples/minimal_demo.py, shortened to a fixed
5s duration instead of running until Ctrl+C.
"""

import time

import numpy as np

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

print("Connecting to Reachy Mini...")
with ReachyMini(media_backend="no_media") as mini:
    print("Connected. Moving to neutral pose...")
    mini.goto_target(create_head_pose(), antennas=[0.0, 0.0], duration=1.0)

    print("Running 5s of gentle head/antenna motion...")
    start = time.time()
    while time.time() - start < 5.0:
        t = time.time()
        antennas_offset = np.deg2rad(20 * np.sin(2 * np.pi * 0.5 * t))
        pitch = np.deg2rad(10 * np.sin(2 * np.pi * 0.5 * t))
        head_pose = create_head_pose(roll=0.0, pitch=pitch, yaw=0.0, degrees=False, mm=False)
        mini.set_target(head=head_pose, antennas=[antennas_offset, antennas_offset])
        time.sleep(0.01)

    print("Returning to neutral pose...")
    mini.goto_target(create_head_pose(), antennas=[0.0, 0.0], duration=1.0)

print("Done. Connection and motion test successful.")
