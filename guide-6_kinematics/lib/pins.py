# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
RW-1 pin map for the Cytron Motion 2350 Pro.

All scripts import their pins from here, so a wiring change is made in one place.
The motor pins are the board's M1 and M2 channels.
"""
import board

# Motor driver channels: M1 = left motor, M2 = right motor
MOTOR_LEFT_PWM_FWD = board.GP9
MOTOR_LEFT_PWM_BWD = board.GP8
MOTOR_RIGHT_PWM_FWD = board.GP10
MOTOR_RIGHT_PWM_BWD = board.GP11

# Encoder channels. A and B must be two consecutive GPIOs (rotaryio uses the
# RP2350's PIO). Swapping A and B reverses the count direction.
ENCODER_LEFT_A = board.GP1
ENCODER_LEFT_B = board.GP0
ENCODER_RIGHT_A = board.GP2
ENCODER_RIGHT_B = board.GP3
