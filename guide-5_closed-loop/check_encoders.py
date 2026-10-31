# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Step 1: check that both encoders count, and count up when the wheel turns forward.

Lift the robot so the wheels spin freely. The script turns each wheel slowly
forward for 3 seconds, one at a time, and prints the encoder positions.
Watch the wheels: each one must turn forward.
"""
import time

import robot
from config import RobotConfig

TEST_PWM = 0.25     # 25% PWM: slow enough to watch the wheel
TEST_TIME = 3.0     # seconds per wheel

cfg = RobotConfig()
motors = robot.make_motors()
encoders = robot.make_encoders(cfg)


def run(left, right, label):
    start_l, start_r = encoders.position_left, encoders.position_right
    motors.update(robot.duty(left), robot.duty(right))
    t_end = time.monotonic() + TEST_TIME
    while time.monotonic() < t_end:
        print("left: {} right: {}".format(encoders.position_left, encoders.position_right))
        time.sleep(0.1)
    motors.stop()
    d_l = encoders.position_left - start_l
    d_r = encoders.position_right - start_r
    print("{}: left counted {}, right counted {}".format(label, d_l, d_r))
    time.sleep(1.0)
    return d_l, d_r


try:
    l_moved, _ = run(TEST_PWM, 0, "Left wheel forward")
    _, r_moved = run(0, TEST_PWM, "Right wheel forward")
    for name, moved in (("Left", l_moved), ("Right", r_moved)):
        if moved > 0:
            print("{} encoder OK".format(name))
        elif moved < 0:
            print("{} wheel counts backward. If the wheel turned backward, swap its motor"
                  " FWD and BWD pins in lib/pins.py; if it turned forward, swap its"
                  " encoder A and B pins.".format(name))
        else:
            print("{} encoder shows no counts: check its wiring".format(name))
finally:
    motors.stop()
