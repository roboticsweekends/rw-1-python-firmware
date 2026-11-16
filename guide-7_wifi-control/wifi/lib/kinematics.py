# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Differential drive kinematics. Pure math, no hardware.

Conventions (the same as in the blog post):
  v - linear speed of the robot's center, m/s, positive = forward
  w - angular speed (omega), rad/s, positive = turning left (counter-clockwise)
  L - track width: distance between the wheel centers, m
  D - wheel diameter, m

Inverse kinematics, from (v, w) to wheel speeds:
    v_left  = v - w * L / 2
    v_right = v + w * L / 2

Forward kinematics, from wheel speeds to (v, w):
    v = (v_right + v_left) / 2
    w = (v_right - v_left) / L
"""
import math


class DiffDrive:
    """
    Converts between body speed (v, w) and wheel speed in RPM.

    :param float wheel_diameter: Wheel diameter D, in meters.
    :param float track_width: Distance between the wheel centers L, in meters.
    """

    def __init__(self, wheel_diameter, track_width):
        self.track_width = track_width
        # Meters the wheel rolls in one revolution
        self.circumference = math.pi * wheel_diameter
        # Unit conversions, computed once instead of on every control pass
        self._to_rpm = 60.0 / self.circumference   # m/s -> revolutions per minute
        self._to_mps = self.circumference / 60.0   # RPM -> m/s at the wheel rim

    def wheel_rpm(self, v, w):
        """
        Inverse kinematics.

        :param float v: Linear speed, m/s.
        :param float w: Angular speed, rad/s.
        :return tuple: (left RPM, right RPM).
        """
        half_turn = w * self.track_width / 2      # m/s added to the right wheel, taken from the left
        return (v - half_turn) * self._to_rpm, (v + half_turn) * self._to_rpm

    def body_speed(self, rpm_left, rpm_right):
        """
        Forward kinematics.

        :param float rpm_left: Left wheel speed, RPM.
        :param float rpm_right: Right wheel speed, RPM.
        :return tuple: (v in m/s, w in rad/s).
        """
        v_left = rpm_left * self._to_mps
        v_right = rpm_right * self._to_mps
        return (v_right + v_left) / 2, (v_right - v_left) / self.track_width

    def wheel_distance(self, revolutions):
        """Meters a wheel rolls in the given number of revolutions."""
        return revolutions * self.circumference


def limit_rpm(rpm_left, rpm_right, max_rpm):
    """
    Scale both wheel speeds down by the same factor if either is above max_rpm.

    Scaling both wheels keeps their ratio, so the robot still drives along the
    same path (the same turn radius), only slower. Clipping only the fast wheel
    would change the radius.

    :return tuple: (left RPM, right RPM, scale). scale is 1.0 when no scaling was needed.
    """
    fastest = max(abs(rpm_left), abs(rpm_right))
    if fastest <= max_rpm:
        return rpm_left, rpm_right, 1.0
    scale = max_rpm / fastest
    return rpm_left * scale, rpm_right * scale, scale
