# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Drive one lap of a LENGTH x WIDTH rectangle, counter-clockwise.

Mark the robot's start pose with two strips of masking tape: one along the
left side of the body, running past its front, and one across the floor at the
front edge. The front-left corner of the body sits where they cross. After the
lap, measure how far that corner ended up from the crossing, and the angle
between the left side of the body and the side strip.

CORNERS selects the corner type:
  "stop"  - drive each side, stop, spin 90 degrees in place, go on
  "round" - drive each corner as a quarter circle of RADIUS without stopping.
            Each side is then RADIUS shorter at both ends. The lap still ends
            on the start pose, so use the same start marks.

Each side and corner ends when the encoders say it's done. The robot doesn't
know where it is on the floor, so every error in D, L or wheel slip adds up
over the lap.
"""
import math
import time

from config import RobotConfig
from drive import Drive

CORNERS = "stop"   # "stop" or "round"
LENGTH = 1.0       # m
WIDTH = 0.5        # m
SPEED = 0.2        # m/s on the sides
TURN_RATE = math.pi / 4   # rad/s for the spins in place ("stop" corners)
RADIUS = 0.15      # m, corner radius for "round" corners
START_DELAY = 5    # seconds to step back from the robot
REPORT = True      # print v and w for Thonny's Plotter


def lap_stop(drive):
    for side in (LENGTH, WIDTH, LENGTH, WIDTH):
        drive.move(SPEED, 0.0, distance=side, report=REPORT)
        drive.move(0.0, TURN_RATE, angle=math.pi / 2, report=REPORT)


def lap_round(drive):
    # Each corner arc takes RADIUS off both ends of a side
    w = SPEED / RADIUS   # w = v / R
    sides = (LENGTH, WIDTH, LENGTH, WIDTH)
    for i, side in enumerate(sides):
        last = i == len(sides) - 1
        drive.move(SPEED, 0.0, distance=side - 2 * RADIUS, stop=False, report=REPORT)
        drive.move(SPEED, w, angle=math.pi / 2, stop=last, report=REPORT)


def main():
    cfg = RobotConfig()
    drive = Drive(cfg)
    print("Rectangle {} x {} m, corners: {}".format(LENGTH, WIDTH, CORNERS))
    print("Starting in {} s".format(START_DELAY))
    time.sleep(START_DELAY)
    start = time.monotonic()
    try:
        if CORNERS == "round":
            lap_round(drive)
        else:
            lap_stop(drive)
    finally:
        drive.stop()
    print("Lap time: {:.1f} s".format(time.monotonic() - start))


main()
