# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Builds RW-1's hardware objects from the pin map and the configuration,
so every script creates motors and encoders the same way.
"""
import pins
from encoder import EncoderReader
from motor_controller import MotorController

PWM_FREQ = 20000   # Hz, above the audible range
DUTY_MAX = 65535   # full PWM duty in CircuitPython units
SPEED_SMOOTHING = 0.5   # 0 = raw encoder speed, closer to 1 = smoother but slower


def make_motors():
    """Return a MotorController for the left (M1) and right (M2) motors."""
    return MotorController(
        pins.MOTOR_LEFT_PWM_FWD,
        pins.MOTOR_LEFT_PWM_BWD,
        pins.MOTOR_RIGHT_PWM_FWD,
        pins.MOTOR_RIGHT_PWM_BWD,
        PWM_FREQ,
        DUTY_MAX,
    )


def make_encoders(cfg):
    """Return an EncoderReader for both wheels, using the configured divisor."""
    return EncoderReader(
        pins.ENCODER_LEFT_A,
        pins.ENCODER_LEFT_B,
        pins.ENCODER_RIGHT_A,
        pins.ENCODER_RIGHT_B,
        cfg.ticks_per_rev,
        smoothing=SPEED_SMOOTHING,
        divisor=cfg.encoder_divisor,
    )


def duty(fraction):
    """Convert a PWM fraction (-1.0 .. 1.0) to a signed duty value."""
    return int(fraction * DUTY_MAX)
