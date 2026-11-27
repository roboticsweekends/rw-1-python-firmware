# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Drive a square, using the wheel encoders to end each side and turn.

    python drive_square.py --side 0.5 --right --host 192.168.4.1
"""
import argparse
import math

from rw1_client import Robot, RobotError, Odometry


def main():
    parser = argparse.ArgumentParser(description="Drive a square using the wheel encoders.")
    parser.add_argument("--host", default="rw-1.local")
    parser.add_argument("--side", type=float, default=0.5, help="side length, m")
    parser.add_argument("--right", action="store_true", help="turn right instead of left")
    args = parser.parse_args()

    with Robot(args.host).connect() as robot:
        odo = Odometry(robot)
        angle = -90 if args.right else 90
        print("Driving a {:.2f} m square, turning {}. Ctrl+C stops.".format(
            args.side, "right" if args.right else "left"))
        try:
            for i in range(4):
                dist, drift = robot.drive_distance(args.side, odo=odo)
                turned = robot.turn_angle(angle, odo=odo)
                print("side {}: {:.3f} m (heading drift {:+.1f} deg), turn {:+.1f} deg".format(
                    i + 1, dist, math.degrees(drift), turned))
        except KeyboardInterrupt:
            print("\nStopped")
        except RobotError as error:
            print(error)
        # leaving the "with" block stops the robot


if __name__ == "__main__":
    main()
