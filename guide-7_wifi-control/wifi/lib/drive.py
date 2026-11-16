# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Drive RW-1 by body speed: linear speed v (m/s) and angular speed w (rad/s).

This is guide 6's lib/drive.py, moved to the Wi-Fi board. The wheel speed
control (feedforward + PI) stays on the controller board, so one call to
Drive.update() now does:

  Measure  - wheel RPM from the controller's telemetry -> forward kinematics -> measured v, w
  Ramp     - move the commanded v, w toward the request, within the acceleration limits
  Convert  - inverse kinematics -> wheel RPM targets, scaled down to the wheel speed limit
  Send     - send the targets to the controller board, which compares, corrects and drives
"""
import math

from kinematics import DiffDrive, limit_rpm


def ramp(current, target, max_change):
    """Move current toward target by at most max_change."""
    if current < target:
        return min(current + max_change, target)
    return max(current - max_change, target)


class Drive:
    """
    Body-speed drive for RW-1: kinematics on top of the controller board.

    :param cfg: RobotConfig of the Wi-Fi board.
    :param controller: controller.Controller, the link to the controller board.
    """

    def __init__(self, cfg, controller):
        self.cfg = cfg
        self.controller = controller
        self.apply_settings()

        # Commanded body speed after the ramp
        self.v_cmd = 0.0
        self.w_cmd = 0.0
        # Measured body speed (forward kinematics of the wheel speeds)
        self.v = 0.0
        self.w = 0.0
        # Wheel targets sent to the controller board, RPM
        self.target_left = 0.0
        self.target_right = 0.0
        self.scale = 1.0   # 1.0, or less when the request was over the wheel speed limit

        self.reset_trip()

    def apply_settings(self):
        """Use the current geometry: call it after D or L changed."""
        self.kin = DiffDrive(self.cfg.wheel_diameter, self.cfg.track_width)

    def wheel_limit(self):
        """
        Fastest wheel target allowed: the wheel speed limit from settings.toml,
        but never more than the controller board's max_rpm.
        """
        max_rpm = self.controller.param("max_rpm", self.cfg.wheel_limit_rpm)
        return min(self.cfg.wheel_limit_rpm, max_rpm)

    def limits(self):
        """
        Fastest straight speed and fastest spin the wheel speed limit allows:
        (v_max in m/s, w_max in rad/s). The web page scales its joystick to these.
        """
        v_max = self.wheel_limit() * math.pi * self.cfg.wheel_diameter / 60
        return v_max, 2 * v_max / self.cfg.track_width

    def update(self, v, w, dt):
        """
        Run one pass.

        :param float v: Requested linear speed, m/s.
        :param float w: Requested angular speed, rad/s.
        :param float dt: Seconds since the previous pass.
        """
        cfg = self.cfg
        ctrl = self.controller

        # Measure
        self.v, self.w = self.kin.body_speed(ctrl.rpm_left, ctrl.rpm_right)

        if not ctrl.ok:
            # No telemetry: the controller board is off, restarting or not
            # wired. Start from standstill when it comes back.
            v = w = 0.0
            self.v_cmd = self.w_cmd = 0.0

        # Ramp: a sudden speed change makes the wheels slip on the floor
        self.v_cmd = ramp(self.v_cmd, v, cfg.max_accel * dt)
        self.w_cmd = ramp(self.w_cmd, w, cfg.max_ang_accel * dt)

        # Convert to wheel targets, within the wheel speed limit
        left, right = self.kin.wheel_rpm(self.v_cmd, self.w_cmd)
        self.target_left, self.target_right, self.scale = limit_rpm(
            left, right, self.wheel_limit())

        # Send: the targets also tell the controller board we're still here
        ctrl.send_targets(self.target_left, self.target_right)

    def stop(self):
        """Stop at once, without the ramp (emergency stop)."""
        self.controller.stop()
        self.v_cmd = 0.0
        self.w_cmd = 0.0
        self.target_left = 0.0
        self.target_right = 0.0

    def reset_trip(self):
        """Start measuring distance and turn angle from here."""
        self._start_left = self.controller.pos_left
        self._start_right = self.controller.pos_right

    def trip(self):
        """
        Distance and turn since reset_trip(), from the encoder counts.

        :return tuple: (distance driven by the robot's center in m,
                        angle turned in rad, positive = left),
                       or (0, 0) while the controller's ticks_per_rev is unknown.
        """
        ticks = self.controller.param("ticks_per_rev")
        if not ticks:
            return 0.0, 0.0
        ctrl = self.controller
        s_left = self.kin.wheel_distance((ctrl.pos_left - self._start_left) / ticks)
        s_right = self.kin.wheel_distance((ctrl.pos_right - self._start_right) / ticks)
        return (s_right + s_left) / 2, (s_right - s_left) / self.kin.track_width
