# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Wheel speed control: hold each wheel at its target RPM.

This is the wheel level of guide 5 and 6, unchanged: feedforward + PI per
wheel, every control pass. make_pid() and wheel_duty() are the functions
from guide 6's lib/drive.py. The rest of guide 6's drive.py (ramp and
kinematics) now runs on the Wi-Fi board, which sends the wheel targets.

One call to Wheels.update() is one pass:

  Measure             - encoders -> wheel RPM
  Compare and correct - feedforward + PI per wheel -> motor duty
  Drive               - send the duty to the motors
"""
import robot
from pid import PID

MIN_RPM = 1.0   # wheel targets below this count as "stopped"


def make_pid(cfg, mode):
    """mode: "open" (feedforward only), "p" (feedforward + P) or "pi" (feedforward + P + I)."""
    kp = 0.0 if mode == "open" else cfg.pid_kp
    ki = cfg.pid_ki if mode == "pi" else 0.0
    return PID(kp=kp, ki=ki, out_min=-robot.DUTY_MAX, out_max=robot.DUTY_MAX)


def wheel_duty(pid, target, rpm, ff, rpm_to_duty, dt):
    """Return the duty for one wheel. A target near 0 stops the wheel."""
    # Kinematics returns floats, so a wheel that should stand still gets a
    # target like 0.0001 RPM instead of exactly 0. Treat that as a stop.
    if abs(target) < MIN_RPM:
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


def _clamp(value, limit):
    return max(-limit, min(limit, value))


class Wheels:
    """
    Both wheels' speed controllers, motors and encoders.

    :param cfg: RobotConfig with the robot's settings.
    :param str mode: Wheel controller, as MODE in guide 5: "open", "p" or "pi".
    """

    def __init__(self, cfg, mode="pi"):
        self.cfg = cfg
        self.mode = mode
        self.motors = robot.make_motors()
        self.encoders = robot.make_encoders(cfg)
        self.apply_settings()

        self.target_left = 0.0    # RPM
        self.target_right = 0.0
        self.rpm_left = 0.0       # measured RPM
        self.rpm_right = 0.0
        self.duty_left = 0        # -DUTY_MAX .. DUTY_MAX
        self.duty_right = 0

    def apply_settings(self):
        """Use the current settings: call it after a gain or max_rpm change."""
        self._rpm_to_duty = robot.DUTY_MAX / self.cfg.max_rpm
        # New controllers start with an empty integral, so a gain change can
        # give a small bump in speed
        self._pid_left = make_pid(self.cfg, self.mode)
        self._pid_right = make_pid(self.cfg, self.mode)

    def set_targets(self, left, right):
        """Set the wheel targets in RPM, limited to max_rpm."""
        limit = self.cfg.max_rpm
        self.target_left = _clamp(left, limit)
        self.target_right = _clamp(right, limit)

    def update(self, dt):
        """Run one pass: measure, compare and correct, drive."""
        cfg = self.cfg
        self.rpm_left, self.rpm_right = self.encoders.update(dt)
        self.duty_left = wheel_duty(self._pid_left, self.target_left, self.rpm_left,
                                    cfg.ff_left, self._rpm_to_duty, dt)
        self.duty_right = wheel_duty(self._pid_right, self.target_right, self.rpm_right,
                                     cfg.ff_right, self._rpm_to_duty, dt)
        self.motors.update(self.duty_left, self.duty_right)

    def stop(self):
        """Zero the targets and let the motors coast."""
        self.target_left = 0.0
        self.target_right = 0.0
        self.duty_left = 0
        self.duty_right = 0
        self.motors.stop()
        self._pid_left.reset()
        self._pid_right.reset()

    def duty_percent(self):
        """Duty of both motors in percent of full PWM, for telemetry."""
        to_pct = 100.0 / robot.DUTY_MAX
        return self.duty_left * to_pct, self.duty_right * to_pct
