# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Check the kinematics on blocks: wheel directions, speeds and the speed limit.

Lift the robot so the wheels spin freely. The script runs three tests, 4
seconds each, and prints the target and the measured RPM of each wheel,
averaged over the last second of the test:

  1. forward   v = 0.2 m/s        both wheels forward, 47.7 RPM
  2. spin left w = pi/4 rad/s     left wheel backward, right wheel forward, 18.3 RPM
  3. too fast  v = 0.7, w = 2.0   both wheels scaled down to the wheel speed limit

The RPM values are for D = 80 mm and L = 195 mm.
"""
import math

from config import RobotConfig
from drive import Drive

TESTS = (
    ("forward", 0.2, 0.0),
    ("spin left", 0.0, math.pi / 4),
    ("too fast", 0.7, 2.0),
)
TEST_PASSES = 200     # 4 s at 20 ms per pass
AVERAGE_PASSES = 50   # average the last 1 s
STOP_PASSES = 50      # 1 s to stop between the tests
TOLERANCE = 0.1       # measured speed within 10% of the target


def check_wheel(name, target, measured):
    """Print one wheel's result and return True if it's within TOLERANCE."""
    if target * measured < 0:
        verdict = "WRONG DIRECTION"
    elif abs(measured - target) > TOLERANCE * abs(target):
        verdict = "SPEED OFF"
    else:
        verdict = "OK"
    print("  {:5} target {:6.1f} RPM  measured {:6.1f} RPM  {}".format(
        name, target, measured, verdict))
    return verdict == "OK"


def main():
    cfg = RobotConfig()
    drive = Drive(cfg)
    all_ok = True
    try:
        for name, v, w in TESTS:
            sum_l = sum_r = 0.0
            for i in range(TEST_PASSES):
                dt = drive.ticker.wait()
                drive.update(v, w, dt)
                if i >= TEST_PASSES - AVERAGE_PASSES:
                    sum_l += drive.rpm_left
                    sum_r += drive.rpm_right
            print("{}: v = {:.2f} m/s, w = {:.2f} rad/s, scale = {:.3f}".format(
                name, v, w, drive.scale))
            all_ok &= check_wheel("left", drive.target_left, sum_l / AVERAGE_PASSES)
            all_ok &= check_wheel("right", drive.target_right, sum_r / AVERAGE_PASSES)
            for _ in range(STOP_PASSES):
                dt = drive.ticker.wait()
                drive.update(0.0, 0.0, dt)
    finally:
        drive.stop()

    print()
    print("All OK" if all_ok else "Some checks failed: see the guide for the fixes")


main()
