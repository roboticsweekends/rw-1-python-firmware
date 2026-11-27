# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Controller board settings: settings.toml defaults, live changes from the web
page, and values saved in NVM (lib/store.py).
"""
import os

import store

# (settings.toml key, attribute name, default, type, min, max, live)
# RobotConfig gets one attribute per line: cfg.max_rpm, cfg.ticks_per_rev, ...
# live=True: can be changed from the web page while the robot runs.
_FIELDS = (
    ("ROBOT_MAX_RPM",         "max_rpm",         200.0,  float, 10.0, 1000.0, True),   # wheel RPM at full PWM
    ("ROBOT_TICKS_PER_REV",   "ticks_per_rev",   1920,   int,   1,    100000, False),  # counts per wheel revolution
    ("ROBOT_ENCODER_DIVISOR", "encoder_divisor", 1,      int,   1,    4,      False),  # rotaryio divisor
    ("ROBOT_FF_LEFT",         "ff_left",         0.8,    float, 0.0,  2.0,    True),   # feedforward correction, left motor
    ("ROBOT_FF_RIGHT",        "ff_right",        0.8,    float, 0.0,  2.0,    True),   # feedforward correction, right motor
    ("ROBOT_PID_KP",          "pid_kp",          0.6,    float, 0.0,  20.0,   True),
    ("ROBOT_PID_KI",          "pid_ki",          3.0,    float, 0.0,  100.0,  True),
    ("CONTROL_PERIOD_MS",     "control_period_ms", 20,   int,   2,    100,    False),  # control loop period
    ("TELEMETRY_EVERY",       "telemetry_every", 1,      int,   1,    10,     True),   # send telemetry every N passes (x period: < CONTROLLER_TIMEOUT)
    ("LINK_BAUD",             "link_baud",       921600, int,   9600, 3000000, False), # serial link speed, both boards
    ("LINK_TIMEOUT",          "link_timeout",    0.3,    float, 0.05, 5.0,    True),   # stop if no targets for this long, s
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


def _check(field, text):
    """Convert text to the field's type and check its range. Return (value, error)."""
    _, _, _, typ, lo, hi, _ = field
    try:
        value = typ(float(text)) if typ is int else typ(text)
    except (ValueError, TypeError):
        return None, "not_a_number"
    if value < lo or value > hi:
        return None, "out_of_range"
    return value, None


class RobotConfig:
    """All tunable controller board parameters in one object."""

    def __init__(self):
        for key, attr, default, typ, _, _, _ in _FIELDS:
            setattr(self, attr, _read(key, default, typ))
        # Values saved from the web page replace the settings.toml ones
        stored = store.load()
        self.saved = []   # names of the settings that come from NVM
        for field in _FIELDS:
            attr = field[1]
            if field[6] and attr in stored:
                value, error = _check(field, stored[attr])
                if error is None:
                    setattr(self, attr, value)
                    self.saved.append(attr)

    def set(self, attr, text):
        """
        Change one live setting.

        :return str | None: An error code ("not_a_number", "out_of_range",
            "not_live" or "unknown"), or None if the value was set.
        """
        for field in _FIELDS:
            if field[1] == attr:
                if not field[6]:
                    return "not_live"
                value, error = _check(field, text)
                if error is None:
                    setattr(self, attr, value)
                return error
        return "unknown"

    def save(self):
        """
        Keep the live values that differ from settings.toml in NVM. Values
        equal to settings.toml aren't saved, so a later edit of
        settings.toml still works for them.
        """
        values = {}
        for key, attr, default, typ, _, _, live in _FIELDS:
            if live and getattr(self, attr) != _read(key, default, typ):
                values[attr] = getattr(self, attr)
        store.save(values)
        self.saved = list(values)

    def reset(self):
        """Forget the saved values and go back to settings.toml."""
        store.clear()
        self.saved = []
        for key, attr, default, typ, _, _, _ in _FIELDS:
            setattr(self, attr, _read(key, default, typ))

    def to_pairs(self):
        """All settings as {attribute name: value}, for a TEXT frame."""
        return {f[1]: getattr(self, f[1]) for f in _FIELDS}

    def live_names(self):
        return [f[1] for f in _FIELDS if f[6]]

    def __str__(self):
        return " ".join("{}={}".format(f[1], getattr(self, f[1])) for f in _FIELDS)
