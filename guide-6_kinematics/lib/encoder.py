# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Encoder reader: reads the two wheel encoders and computes wheel RPM.
"""
import rotaryio


class EncoderReader:
    """
    Read two quadrature encoders and compute the speed of each wheel in RPM.

    :param pin_left_a: Left encoder channel A (e.g. ``board.GP1``).
    :param pin_left_b: Left encoder channel B.
    :param pin_right_a: Right encoder channel A.
    :param pin_right_b: Right encoder channel B.
    :param int ticks_per_rev: Encoder counts per wheel revolution.
    :param float smoothing: 0 = raw speed, closer to 1 = smoother but slower to react.
    :param int divisor: Encoder edges per count; 1 counts all four edges of each pulse cycle
        (see ``rotaryio.IncrementalEncoder``).
    """

    def __init__(
        self,
        pin_left_a,
        pin_left_b,
        pin_right_a,
        pin_right_b,
        ticks_per_rev,
        *,
        smoothing,
        divisor,
    ):
        self._enc_l = rotaryio.IncrementalEncoder(pin_left_a, pin_left_b, divisor=divisor)
        self._enc_r = rotaryio.IncrementalEncoder(pin_right_a, pin_right_b, divisor=divisor)
        self._ticks_per_rev = ticks_per_rev
        self._smoothing = smoothing
        self._last_pos_l = self._enc_l.position
        self._last_pos_r = self._enc_r.position
        self._rpm_l = 0.0
        self._rpm_r = 0.0

    def update(self, dt):
        """
        Measure the wheel speeds from the counts added since the last update.

        :param float dt: Seconds since the previous update.
        :return tuple: (left RPM, right RPM), smoothed.
        """
        pos_l = self._enc_l.position
        pos_r = self._enc_r.position

        # counts per second -> revolutions per minute
        to_rpm = 60.0 / (self._ticks_per_rev * dt)
        raw_l = (pos_l - self._last_pos_l) * to_rpm
        raw_r = (pos_r - self._last_pos_r) * to_rpm
        self._last_pos_l = pos_l
        self._last_pos_r = pos_r

        # Exponential smoothing: keep part of the old value, mix in the new one
        s = self._smoothing
        self._rpm_l = s * self._rpm_l + (1.0 - s) * raw_l
        self._rpm_r = s * self._rpm_r + (1.0 - s) * raw_r
        return self._rpm_l, self._rpm_r

    @property
    def position_left(self):
        """Left encoder position (counts)."""
        return self._enc_l.position

    @property
    def position_right(self):
        """Right encoder position (counts)."""
        return self._enc_r.position
