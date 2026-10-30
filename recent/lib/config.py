# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Robot configuration loaded from ``settings.toml``.

Edit ``settings.toml`` on the CIRCUITPY drive to change a value; the board
restarts and the new value is used. Float values must be quoted there,
because CircuitPython's ``settings.toml`` only supports strings and integers.
"""
import os

# (settings.toml key, attribute name, default, type)
# RobotConfig gets one attribute per line: cfg.max_rpm, cfg.ticks_per_rev, ...
_FIELDS = (
    ("ROBOT_MAX_RPM",         "max_rpm",         200.0,  float),  # wheel RPM at full PWM
    ("ROBOT_TICKS_PER_REV",   "ticks_per_rev",   1920,   int),    # counts per wheel revolution
    ("ROBOT_ENCODER_DIVISOR", "encoder_divisor", 2,      int),    # rotaryio divisor
    ("ROBOT_FF_LEFT",         "ff_left",         1.0,    float),  # feedforward correction, left motor
    ("ROBOT_FF_RIGHT",        "ff_right",        1.0,    float),  # feedforward correction, right motor
    ("ROBOT_PID_KP",          "pid_kp",          0.9,    float),
    ("ROBOT_PID_KI",          "pid_ki",          5.2,    float),
)


def _read(key, default, typ):
    """Return the value of ``key`` from settings.toml, or ``default`` if it's missing or invalid."""
    try:
        raw = os.getenv(key)
    except (ValueError, SyntaxError):
        raw = None
    if raw is None:
        return default
    try:
        return typ(float(raw)) if typ is int else typ(raw)
    except (ValueError, TypeError):
        return default


class RobotConfig:
    """All tunable robot parameters in one object."""

    def __init__(self):
        for key, attr, default, typ in _FIELDS:
            setattr(self, attr, _read(key, default, typ))

    def __str__(self):
        return " ".join("{}={}".format(f[1], getattr(self, f[1])) for f in _FIELDS)
