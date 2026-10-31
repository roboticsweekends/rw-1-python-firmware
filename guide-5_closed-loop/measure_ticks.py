# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Step 2: measure encoder counts per wheel revolution.

Put a piece of tape on the left wheel as a mark and lift the robot. The script
turns both wheels slowly for RUN_TIME seconds. Count the revolutions of the left
wheel while it runs and type the number when asked.
Run it from Thonny: the script reads your answer from Thonny's shell.
"""
import time

import robot
from config import RobotConfig

TEST_PWM = 0.15     # slow, so the revolutions are easy to count
RUN_TIME = 20.0     # seconds

cfg = RobotConfig()
motors = robot.make_motors()
encoders = robot.make_encoders(cfg)

print("Counting starts in 3 seconds. Watch the tape mark on the wheel.")
time.sleep(3.0)
start_l, start_r = encoders.position_left, encoders.position_right
try:
    motors.update(robot.duty(TEST_PWM), robot.duty(TEST_PWM))
    time.sleep(RUN_TIME)
finally:
    motors.stop()

d_l = encoders.position_left - start_l
d_r = encoders.position_right - start_r
print("Left counted {}, right counted {} (divisor={})".format(d_l, d_r, cfg.encoder_divisor))
revs = float(input("How many full revolutions did the left wheel make? "))
if revs > 0:
    print("Counts per wheel revolution: {:.0f}".format(d_l / revs))
    print('Put it in settings.toml as ROBOT_TICKS_PER_REV={:.0f}'.format(d_l / revs))
