# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Calibrate the track width on the floor. Calibrate the wheel diameter first.

Stick a strip of masking tape on the floor along the robot's front edge,
sticking out to the robot's right. The robot spins in place to the left until
the encoders say it has turned TURNS full turns, then stops. Measure the angle
between the front edge and the tape in degrees: positive if the robot turned
past the tape (too far), negative if it stopped short.

The robot really turned TURNS * 360 degrees plus that error. If it turned too
far, the wheels traveled the counted arc but the robot turned more, so the
real track width is smaller than the setting:
    L_new = L * counted angle / (TURNS * 360 + error)
"""
import math
import time

from config import RobotConfig
from drive import Drive

TURNS = 5         # more turns make a small error easier to read
SPIN_RATE = 1.0   # rad/s, slow enough to keep the wheels from slipping
START_DELAY = 5   # seconds to step back from the robot


def main():
    cfg = RobotConfig()
    drive = Drive(cfg)
    print("Track width now: {:.4f} m".format(cfg.track_width))
    print("Starting in {} s".format(START_DELAY))
    time.sleep(START_DELAY)
    try:
        drive.move(0.0, SPIN_RATE, angle=TURNS * 2 * math.pi)
    finally:
        drive.stop()
    time.sleep(0.5)   # let the robot settle before reading the counts
    _, counted = drive.trip()
    print("The encoders counted {:.1f} degrees ({:.3f} turns)".format(
        math.degrees(counted), counted / (2 * math.pi)))
    print("The robot should be {:.1f} degrees past the tape".format(
        math.degrees(counted - TURNS * 2 * math.pi)))

    error_deg = float(input("Measured angle past the tape, degrees (negative if short): "))
    # The real angle is TURNS full turns plus the measured error
    real = TURNS * 2 * math.pi + math.radians(error_deg)
    new_l = cfg.track_width * counted / real
    print()
    print("Copy this line into settings.toml:")
    print('ROBOT_TRACK_WIDTH="{:.4f}"'.format(new_l))


main()
