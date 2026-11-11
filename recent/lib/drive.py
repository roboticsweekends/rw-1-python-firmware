# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Drive RW-1 by body speed: linear speed v (m/s) and angular speed w (rad/s).

Builds on the wheel speed control from part 5: make_pid() and wheel_duty()
are the functions from part 5's code.py, moved here so that every script
drives the wheels the same way. One call to Drive.update() is one pass of the
control loop:

  Measure             - encoders -> wheel RPM -> forward kinematics -> measured v, w
  Ramp                - move the commanded v, w toward the request, within the acceleration limits
  Convert             - inverse kinematics -> wheel RPM targets, scaled down to the wheel speed limit
  Compare and correct - feedforward + PI per wheel, as in part 5 -> motor duty
  Drive               - send the duty to the motors
"""
import robot
from kinematics import DiffDrive, limit_rpm
from pid import PID
from ticker import Ticker

CONTROL_PERIOD_NS = 20_000_000   # 20 ms (50 Hz control loop), in nanoseconds
MIN_RPM = 1.0                    # wheel targets below this count as "stopped"


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


def ramp(current, target, max_change):
    """Move current toward target by at most max_change."""
    if current < target:
        return min(current + max_change, target)
    return max(current - max_change, target)


class Drive:
    """
    Body-speed drive for RW-1: kinematics on top of the wheel speed controllers.

    :param cfg: RobotConfig with the robot's settings.
    :param str mode: Wheel controller, as MODE in part 5: "open", "p" or "pi".
    """

    def __init__(self, cfg, mode="pi"):
        self.cfg = cfg
        self.kin = DiffDrive(cfg.wheel_diameter, cfg.track_width)
        self.motors = robot.make_motors()
        self.encoders = robot.make_encoders(cfg)
        self.ticker = Ticker(CONTROL_PERIOD_NS)
        self._rpm_to_duty = robot.DUTY_MAX / cfg.max_rpm
        self._pid_left = make_pid(cfg, mode)
        self._pid_right = make_pid(cfg, mode)

        # Commanded body speed after the ramp
        self.v_cmd = 0.0
        self.w_cmd = 0.0
        # Measured body speed (forward kinematics of the encoder speeds)
        self.v = 0.0
        self.w = 0.0
        # Wheel speeds, RPM
        self.target_left = 0.0
        self.target_right = 0.0
        self.rpm_left = 0.0
        self.rpm_right = 0.0
        self.scale = 1.0   # 1.0, or less when the request was over the wheel speed limit

        self.reset_trip()

    def update(self, v, w, dt):
        """
        Run one pass of the control loop.

        :param float v: Requested linear speed, m/s.
        :param float w: Requested angular speed, rad/s.
        :param float dt: Seconds since the previous pass.
        """
        cfg = self.cfg

        # Measure
        self.rpm_left, self.rpm_right = self.encoders.update(dt)
        self.v, self.w = self.kin.body_speed(self.rpm_left, self.rpm_right)

        # Ramp: a sudden speed change makes the wheels slip on the floor
        self.v_cmd = ramp(self.v_cmd, v, cfg.max_accel * dt)
        self.w_cmd = ramp(self.w_cmd, w, cfg.max_ang_accel * dt)

        # Convert to wheel targets, within the wheel speed limit
        left, right = self.kin.wheel_rpm(self.v_cmd, self.w_cmd)
        self.target_left, self.target_right, self.scale = limit_rpm(
            left, right, cfg.wheel_limit_rpm)

        # Compare and correct
        duty_left = wheel_duty(self._pid_left, self.target_left, self.rpm_left,
                               cfg.ff_left, self._rpm_to_duty, dt)
        duty_right = wheel_duty(self._pid_right, self.target_right, self.rpm_right,
                                cfg.ff_right, self._rpm_to_duty, dt)

        # Drive
        self.motors.update(duty_left, duty_right)

    def reset_trip(self):
        """Start measuring distance and turn angle from here."""
        self._start_left = self.encoders.position_left
        self._start_right = self.encoders.position_right

    def trip(self):
        """
        Distance and turn since reset_trip(), from the encoder counts.

        :return tuple: (distance driven by the robot's center in m,
                        angle turned in rad, positive = left).
        """
        ticks = self.cfg.ticks_per_rev
        s_left = self.kin.wheel_distance((self.encoders.position_left - self._start_left) / ticks)
        s_right = self.kin.wheel_distance((self.encoders.position_right - self._start_right) / ticks)
        return (s_right + s_left) / 2, (s_right - s_left) / self.kin.track_width

    def move(self, v, w, distance=None, angle=None, stop=True, report=False):
        """
        Drive at (v, w) until the robot's center has driven ``distance`` meters
        or the robot has turned ``angle`` radians. Give one of the two.

        With stop=True the robot slows down within the acceleration limits and
        stops at the end. With stop=False it keeps its speed, so the next move()
        continues smoothly; a turn with stop=False expects the next move to
        drive straight.

        :param bool report: Print the Plotter line on every pass.
        """
        self.reset_trip()
        self.ticker.reset()
        braking = False
        while True:
            dt = self.ticker.wait()
            traveled, turned = self.trip()
            if distance is not None:
                remaining = abs(distance) - abs(traveled)
                # distance needed to stop from the current speed: v^2 / (2a)
                stopping = self.v_cmd * self.v_cmd / (2 * self.cfg.max_accel)
            else:
                remaining = abs(angle) - abs(turned)
                stopping = self.w_cmd * self.w_cmd / (2 * self.cfg.max_ang_accel)

            if stop:
                if remaining <= stopping:
                    braking = True
            elif remaining <= (stopping if angle is not None else 0):
                # Keep the speed for the next move. A turn ends early by the
                # angle the robot still turns while w ramps down for the next,
                # straight move.
                break

            if braking:
                self.update(0.0, 0.0, dt)
                if self.v_cmd == 0 and self.w_cmd == 0:
                    break
            else:
                self.update(v, w, dt)
            if report:
                self.print_status()

    def stop(self):
        """Stop the motors (coast) and reset the commanded speed."""
        self.motors.stop()
        self.v_cmd = 0.0
        self.w_cmd = 0.0
        self._pid_left.reset()
        self._pid_right.reset()

    def print_status(self):
        """
        Print commanded and measured v and w for Thonny's Plotter.

        The commanded values are after the ramp and the speed limit scaling,
        so they show what the wheels were actually asked to do.
        """
        print("v_cmd: {:.3f} v: {:.3f} w_cmd: {:.3f} w: {:.3f}".format(
            self.v_cmd * self.scale, self.v, self.w_cmd * self.scale, self.w))

    def print_wheels(self):
        """Print target and measured RPM of both wheels, as code.py did in part 5."""
        print("target_l: {:.0f} left: {:.1f} target_r: {:.0f} right: {:.1f}".format(
            self.target_left, self.rpm_left, self.target_right, self.rpm_right))
