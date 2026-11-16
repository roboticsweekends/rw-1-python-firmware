# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Drive a square from the PC, using the wheel encoders to know when each side
and each turn is done.

    python drive_square.py                       # 0.5 m sides, turning left
    python drive_square.py --side 1.0 --right --host 192.168.4.1

Put the robot on the floor with at least side + 0.3 m of free space ahead
and to the left (or right). Press Ctrl+C to stop it at any time.

How it works: the robot sends its encoder counts (pos_l, pos_r) 50 times a
second. From them this script works out how far the robot drove and how
far it turned (the same odometry as guide 6), and asks for:
  - straight: v, with a small w that keeps the heading straight;
  - turn: w.
Near the end it asks for less and less speed, never more than the robot
can still stop from in the distance left: v = sqrt(2 * a * distance left),
where a is a bit below the robot's own acceleration limit (ROBOT_MAX_ACCEL,
ROBOT_MAX_ANG_ACCEL). So the robot's speed ramp can follow, and it stops
close to the mark instead of rolling past it.

Telemetry reaches the PC in batches every 0.1 s, so the counts are up to
0.1 s old. The script adds what the robot drove in that time (measured
speed x LAG) before deciding.
"""
import argparse
import math
import time

from rw1_client import Robot, RobotError

V = 0.2            # m/s on the straights
W = 1.2            # rad/s in the turns
V_MIN = 0.03       # slowest speeds near the end, so the robot still gets there
W_MIN = 0.2
BRAKE = 0.7        # brake with 70 % of the robot's acceleration limits
LAG = 0.1          # s: how old the telemetry can be when it arrives
K_HEADING = 3.0    # rad/s of correction per rad of heading error
PERIOD = 0.05      # s between requests


class Odometry:
    """Distance and heading from the encoder counts."""

    def __init__(self, robot):
        diameter, self.track, ticks = robot.wheel_settings()
        self.m_per_tick = math.pi * diameter / ticks
        p = robot.params()["wifi_board"]
        self.accel = BRAKE * p["max_accel"]["value"]           # m/s^2
        self.ang_accel = BRAKE * p["max_ang_accel"]["value"]   # rad/s^2
        self.robot = robot
        self.start = self.counts()

    def counts(self):
        s = self.robot.sample
        return s["pos_l"], s["pos_r"]

    def since(self, start, ahead=0.0):
        """
        (distance m, turn rad) since the counts in start. With ahead > 0,
        also what the robot drives in the next `ahead` seconds at its
        measured speed.
        """
        left, right = self.counts()
        s_l = (left - start[0]) * self.m_per_tick
        s_r = (right - start[1]) * self.m_per_tick
        s = self.robot.sample
        return ((s_l + s_r) / 2 + s["v"] * ahead,
                (s_r - s_l) / self.track + s["w"] * ahead)


def check(robot):
    """Give up if the robot refused a request (e.g. STOP pressed on the web page)."""
    if robot.errors:
        raise RuntimeError("the robot refused: " + robot.errors[-1])


def wait_still(robot, seconds=0.4):
    """Ask for 0 for a moment, so the robot comes to rest before the next move."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        robot.drive(0, 0)
        time.sleep(PERIOD)


def straight(robot, odo, length):
    start = odo.counts()
    while True:
        dist, heading = odo.since(start, LAG)
        left = length - dist
        if left <= 0:
            break
        check(robot)
        v = max(V_MIN, min(V, math.sqrt(2 * odo.accel * left)))
        robot.drive(v, -K_HEADING * heading)
        time.sleep(PERIOD)
    wait_still(robot)
    return odo.since(start)


def turn(robot, odo, angle):
    start = odo.counts()
    sign = 1 if angle > 0 else -1
    while True:
        _, turned = odo.since(start, LAG)
        left = abs(angle) - sign * turned
        if left <= 0:
            break
        check(robot)
        w = max(W_MIN, min(W, math.sqrt(2 * odo.ang_accel * left)))
        robot.drive(0, sign * w)
        time.sleep(PERIOD)
    wait_still(robot)
    return odo.since(start)[1]


def main():
    parser = argparse.ArgumentParser(description="Drive a square using the wheel encoders.")
    parser.add_argument("--host", default="rw-1.local")
    parser.add_argument("--side", type=float, default=0.5, help="side length, m")
    parser.add_argument("--right", action="store_true", help="turn right instead of left")
    args = parser.parse_args()

    with Robot(args.host).connect() as robot:
        while robot.sample is None:            # first telemetry
            time.sleep(0.05)
        odo = Odometry(robot)
        angle = math.radians(-90 if args.right else 90)
        print("Driving a {:.2f} m square, turning {}. Ctrl+C stops.".format(
            args.side, "right" if args.right else "left"))
        try:
            for i in range(4):
                dist, drift = straight(robot, odo, args.side)
                turned = turn(robot, odo, angle)
                print("side {}: {:.3f} m (heading drift {:+.1f} deg), turn {:+.1f} deg".format(
                    i + 1, dist, math.degrees(drift), math.degrees(turned)))
        except KeyboardInterrupt:
            print("\nStopped")
        except (RuntimeError, RobotError) as error:
            print(error)
        # leaving the "with" block stops the robot


if __name__ == "__main__":
    main()
