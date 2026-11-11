# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
PWM motor driver: sends a signed duty to each of the two H-bridge channels.
"""
import pwmio


class MotorController:
    """
    Dual motor PWM driver for two H-bridge channels.

    Positive duty drives a motor's forward pin, negative duty its backward pin.

    :param pin_l_fwd: Left motor forward pin (e.g. ``board.GP9``).
    :param pin_l_bwd: Left motor backward pin.
    :param pin_r_fwd: Right motor forward pin.
    :param pin_r_bwd: Right motor backward pin.
    :param int frequency: PWM frequency in Hz for all four outputs.
    :param int duty_limit: Largest duty value; ``update`` clamps to -duty_limit .. duty_limit.
    """

    def __init__(self, pin_l_fwd, pin_l_bwd, pin_r_fwd, pin_r_bwd, frequency, duty_limit):
        self._duty_limit = duty_limit
        self._pwm_l_fwd = pwmio.PWMOut(pin_l_fwd, frequency=frequency, duty_cycle=0)
        self._pwm_l_bwd = pwmio.PWMOut(pin_l_bwd, frequency=frequency, duty_cycle=0)
        self._pwm_r_fwd = pwmio.PWMOut(pin_r_fwd, frequency=frequency, duty_cycle=0)
        self._pwm_r_bwd = pwmio.PWMOut(pin_r_bwd, frequency=frequency, duty_cycle=0)

    def _apply(self, duty, pwm_fwd, pwm_bwd):
        lim = self._duty_limit
        duty = int(max(-lim, min(lim, duty)))
        if duty >= 0:
            pwm_fwd.duty_cycle = duty
            pwm_bwd.duty_cycle = 0
        else:
            pwm_fwd.duty_cycle = 0
            pwm_bwd.duty_cycle = -duty

    def update(self, left_duty, right_duty):
        """Apply signed duty to left and right motors."""
        self._apply(left_duty, self._pwm_l_fwd, self._pwm_l_bwd)
        self._apply(right_duty, self._pwm_r_fwd, self._pwm_r_bwd)

    def stop(self):
        """Set all PWMs to 0 (coast)."""
        self.update(0, 0)
