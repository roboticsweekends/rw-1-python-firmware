# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
PI controller with feedforward. Pure logic, no hardware.

RW-1 uses one per wheel to hold the wheel speed:

    output = feedforward + Kp * error + Ki * integral(error)
"""


class PID:
    """
    PI controller with feedforward, output limits and integral anti-windup.

    :param float kp: Proportional gain.
    :param float ki: Integral gain.
    :param float out_min: Lowest output value.
    :param float out_max: Highest output value.
    """

    def __init__(self, kp, ki, out_min, out_max):
        self._kp = float(kp)
        self._ki = float(ki)
        self._out_min = float(out_min)
        self._out_max = float(out_max)
        self._integral = 0.0

    def reset(self):
        """Forget the integral, so the next start is clean."""
        self._integral = 0.0

    def update(self, setpoint, measurement, dt, feedforward=0.0):
        """
        Compute the control output.

        :param float setpoint: Target value.
        :param float measurement: Measured value, in the same units as the setpoint.
        :param float dt: Seconds since the previous update.
        :param float feedforward: Output estimate added to the P and I terms. Default 0.
        :return float: Output, limited to out_min .. out_max.
        """
        error = setpoint - measurement
        integral = self._integral + error * dt
        out = feedforward + self._kp * error + self._ki * integral

        # Anti-windup: when the output is already at a limit, don't let the
        # integral push it further. At full duty a bigger integral can't help,
        # and it would make the wheel overshoot once the target is reachable.
        pushing_up = out > self._out_max and error > 0
        pushing_down = out < self._out_min and error < 0
        if not (pushing_up or pushing_down):
            self._integral = integral

        return max(self._out_min, min(self._out_max, out))
