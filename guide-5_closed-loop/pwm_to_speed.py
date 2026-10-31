# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Step 3: measure how fast each wheel turns at a given PWM (open loop).

Lift the robot. The script steps the PWM from 10% to 100% on both motors,
waits for the speed to settle at each step, and prints the average RPM.
At the end it suggests ROBOT_MAX_RPM, ROBOT_FF_LEFT and ROBOT_FF_RIGHT
for settings.toml.
"""
import time

import robot
from config import RobotConfig

STEPS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
SETTLE_TIME = 1.0       # seconds to let the speed settle after a step
MEASURE_TIME = 1.0      # seconds to average over
PERIOD = 0.02           # 20 ms, same as the control loop
FF_REFERENCE = 0.6      # PWM step used to calculate the feedforward correction

cfg = RobotConfig()
motors = robot.make_motors()
encoders = robot.make_encoders(cfg)
last_time = time.monotonic_ns()


def measure():
    """Update the encoder speeds after one PERIOD and return (left RPM, right RPM)."""
    global last_time
    time.sleep(PERIOD)
    now = time.monotonic_ns()
    dt = (now - last_time) / 1_000_000_000   # seconds since the last update
    last_time = now
    return encoders.update(dt)


def average_rpm():
    """Average both wheel speeds over MEASURE_TIME seconds."""
    sum_l = sum_r = 0.0
    n = 0
    t_end = time.monotonic() + MEASURE_TIME
    while time.monotonic() < t_end:
        rpm_l, rpm_r = measure()
        sum_l += rpm_l
        sum_r += rpm_r
        n += 1
    return sum_l / n, sum_r / n


results = {}
try:
    for pwm in STEPS:
        motors.update(robot.duty(pwm), robot.duty(pwm))
        t_end = time.monotonic() + SETTLE_TIME
        while time.monotonic() < t_end:   # keep the speed estimate running while settling
            measure()
        rpm_l, rpm_r = average_rpm()
        results[pwm] = (rpm_l, rpm_r)
        print("pwm: {:.0f} left: {:.1f} right: {:.1f}".format(pwm * 100, rpm_l, rpm_r))
finally:
    motors.stop()

full_l, full_r = results[1.0]
max_rpm = min(full_l, full_r)          # the slower wheel sets the top speed
ref_l, ref_r = results[FF_REFERENCE]
print()
if ref_l <= 0 or ref_r <= 0:
    print("A wheel didn't turn forward at {:.0f}% PWM: run check_encoders.py first".format(
        FF_REFERENCE * 100))
else:
    ff_l = FF_REFERENCE * max_rpm / ref_l
    ff_r = FF_REFERENCE * max_rpm / ref_r
    print("Copy these lines into settings.toml:")
    print('ROBOT_MAX_RPM="{:.1f}"'.format(max_rpm))
    print('ROBOT_FF_LEFT="{:.3f}"'.format(ff_l))
    print('ROBOT_FF_RIGHT="{:.3f}"'.format(ff_r))
