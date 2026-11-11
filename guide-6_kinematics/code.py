# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
RW-1 body speed control: drive with linear speed v and angular speed w.

Builds on part 5's wheel speed control (feedforward + PI on each wheel, every
20 ms). lib/drive.py ramps v and w, converts them to wheel RPM targets with
inverse kinematics, and the wheel speed controllers hold those targets.

MODE selects the wheel controller, as in part 5:
  "open" - feedforward only (open loop)
  "p"    - feedforward + P
  "pi"   - feedforward + P + I

The robot follows the path defined in PROFILE, a list of (seconds, v in m/s, w in rad/s) steps.
PLOT selects what it prints for Thonny's Plotter:
  "body"   - commanded and measured v and w
  "wheels" - target and measured RPM of both wheels, as in part 5
"""
from config import RobotConfig
from drive import Drive

MODE = "pi"
PLOT = "body"
PRINT_EVERY = 1   # print every loop (every 20 ms)

# Robot's path.
# (duration in seconds, v in m/s, w in rad/s)
# The steps cover what the robot will do later: starts, curves, turning on the
# spot, reversing and a command over the speed limit.
# Positive v = forward, positive w = turning left (counter-clockwise).
PROFILE = (
    (1.0, 0.0, 0.0),        # stand still
    (3.0, 0.2, 0.0),        # straight: 47.7 RPM on both wheels
    (3.0, 0.2, 1.0),        # curve to the left, radius 0.2 m
    (3.0, 0.0975, 1.0),     # pivot: v = w * L / 2, the left wheel stands still
    (3.0, 0.0, 0.785),      # spin in place at pi/4 rad/s: -18.3 / +18.3 RPM
    (3.0, -0.2, 0.0),       # reverse
    (3.0, 0.7, 2.0),        # over the limit: both wheels scaled down, same radius
    (2.0, 0.0, 0.0),        # stop
)


def main():
    cfg = RobotConfig()
    print("RW-1 body speed control, mode:", MODE)
    print(cfg)

    drive = Drive(cfg, MODE)
    loop = 0

    try:
        for duration, target_v, target_w in PROFILE:
            elapsed = 0.0
            while elapsed < duration:
                # Wait for the next pass (lib/ticker.py, the part 5 timing)
                dt = drive.ticker.wait()
                elapsed += dt

                # Measure, ramp, convert, compare and correct, drive
                drive.update(target_v, target_w, dt)

                # Report
                loop += 1
                if loop % PRINT_EVERY == 0:
                    if PLOT == "wheels":
                        drive.print_wheels()
                    else:
                        drive.print_status()
    finally:
        drive.stop()
    print("Done")


main()
