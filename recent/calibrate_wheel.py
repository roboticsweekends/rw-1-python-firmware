# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Calibrate the wheel diameter on the floor.

Stick a start line across the floor with masking tape and put the robot with
its front edge on it, facing along at least 2.5 m of clear floor. The robot
drives straight until the encoders say it has gone DISTANCE meters, then
stops. Measure how far the front edge really moved and type it in: the script
prints the corrected ROBOT_WHEEL_DIAMETER.

If the encoders count 2.00 m but the robot really drove 1.97 m, each wheel
revolution covers less ground than the code thinks, so the diameter is smaller:
    D_new = D * measured / counted
"""
import time

from config import RobotConfig
from drive import Drive

DISTANCE = 2.0    # m, as counted by the encoders
SPEED = 0.2       # m/s, slow enough to keep the wheels from slipping
START_DELAY = 5   # seconds to step back from the robot


def main():
    cfg = RobotConfig()
    drive = Drive(cfg)
    print("Wheel diameter now: {:.4f} m".format(cfg.wheel_diameter))
    print("Starting in {} s".format(START_DELAY))
    time.sleep(START_DELAY)
    try:
        drive.move(SPEED, 0.0, distance=DISTANCE)
    finally:
        drive.stop()
    time.sleep(0.5)   # let the robot settle before reading the counts
    counted, _ = drive.trip()
    print("The encoders counted {:.3f} m".format(counted))

    measured = float(input("Measured distance in meters: "))
    new_d = cfg.wheel_diameter * measured / counted
    print()
    print("Copy this line into settings.toml:")
    print('ROBOT_WHEEL_DIAMETER="{:.4f}"'.format(new_d))


main()
