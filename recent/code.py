# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
RW-1 wheel speed control: feedforward + PI on each wheel, every 20 ms.

MODE selects the controller, the same three steps as in the blog post:
  "open" - feedforward only (open loop)
  "p"    - feedforward + P
  "pi"   - feedforward + P + I

The robot follows PROFILE, a list of (seconds, left RPM, right RPM) steps,
and prints the target and both measured speeds for Thonny's Plotter.
"""
import time

import robot
from config import RobotConfig
from pid import PID

MODE = "pi"
CONTROL_PERIOD_NS = 20_000_000   # 20 ms (50 Hz control loop), in nanoseconds
PRINT_EVERY = 1                  # print every loop (every 20 ms)
NS_PER_S = 1_000_000_000

# (duration in seconds, left target RPM, right target RPM)
PROFILE = (
    (1.0, 0, 0),
    (4.0, 100, 100),
    (4.0, 60, 60),
    (4.0, 100, 60),
    (2.0, 0, 0),
)


def make_pid(cfg):
    kp = 0.0 if MODE == "open" else cfg.pid_kp
    ki = cfg.pid_ki if MODE == "pi" else 0.0
    return PID(kp=kp, ki=ki, out_min=-robot.DUTY_MAX, out_max=robot.DUTY_MAX)


def wheel_duty(pid, target, rpm, ff, rpm_to_duty, dt):
    """Return the duty for one wheel. A target of 0 stops the wheel."""
    if target == 0:
        pid.reset()
        return 0
    # Speeds are scaled to duty units, so the gains don't depend on the
    # motor's top speed: with Kp = 1, an error of max_rpm adds full duty.
    return pid.update(
        target * rpm_to_duty,
        rpm * rpm_to_duty,
        dt,
        feedforward=ff * target * rpm_to_duty,
    )


def main():
    cfg = RobotConfig()
    print("RW-1 speed control, mode:", MODE)
    print(cfg)

    rpm_to_duty = robot.DUTY_MAX / cfg.max_rpm
    motors = robot.make_motors()
    encoders = robot.make_encoders(cfg)
    pid_left = make_pid(cfg)
    pid_right = make_pid(cfg)

    # Times are whole nanoseconds from time.monotonic_ns(). time.monotonic()
    # returns a float that loses precision after the board has been on for
    # about an hour, too coarse for a 20 ms loop.
    last_time = time.monotonic_ns()
    next_control_time = last_time
    loop = 0

    try:
        for duration, target_left, target_right in PROFILE:
            step_end = next_control_time + int(duration * NS_PER_S)
            while next_control_time < step_end:
                # Wait for the next pass
                time.sleep(max(0, next_control_time - time.monotonic_ns()) / NS_PER_S)
                now = time.monotonic_ns()
                dt = (now - last_time) / NS_PER_S   # seconds since the last pass
                last_time = now
                next_control_time += CONTROL_PERIOD_NS
                if next_control_time < now:
                    # This pass ran late: skip the missed passes instead of
                    # running them back to back
                    next_control_time = now + CONTROL_PERIOD_NS

                # Measure
                rpm_left, rpm_right = encoders.update(dt)

                # Compare and correct
                duty_left = wheel_duty(pid_left, target_left, rpm_left, cfg.ff_left, rpm_to_duty, dt)
                duty_right = wheel_duty(pid_right, target_right, rpm_right, cfg.ff_right, rpm_to_duty, dt)

                # Drive
                motors.update(duty_left, duty_right)

                # Report
                loop += 1
                if loop % PRINT_EVERY == 0:
                    print("target_l: {:.0f} left: {:.1f} target_r: {:.0f} right: {:.1f}".format(
                        target_left, rpm_left, target_right, rpm_right))
    finally:
        motors.stop()
    print("Done")


main()
