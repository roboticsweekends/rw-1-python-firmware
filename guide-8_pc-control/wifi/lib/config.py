# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Wi-Fi board settings: settings.toml defaults, live changes from the web
page, and values saved in NVM (lib/store.py).
"""
import os

import store

# (settings.toml key, attribute name, default, type, min, max, live)
# RobotConfig gets one attribute per line: cfg.wheel_diameter, cfg.track_width, ...
# live=True: can be changed from the web page while the robot runs.
_FIELDS = (
    ("ROBOT_WHEEL_DIAMETER",  "wheel_diameter",  0.080,  float, 0.01, 0.5,   True),   # wheel diameter D, m
    ("ROBOT_TRACK_WIDTH",     "track_width",     0.195,  float, 0.05, 1.0,   True),   # wheel center to center L, m
    ("ROBOT_WHEEL_LIMIT_RPM", "wheel_limit_rpm", 170.0,  float, 1.0,  1000.0, True),  # fastest wheel target kinematics may ask for
    ("ROBOT_MAX_ACCEL",       "max_accel",       0.5,    float, 0.05, 10.0,  True),   # linear acceleration limit, m/s^2
    ("ROBOT_MAX_ANG_ACCEL",   "max_ang_accel",   3.0,    float, 0.1,  50.0,  True),   # angular acceleration limit, rad/s^2
    ("DRIVE_PERIOD_MS",       "drive_period_ms", 20,     int,   5,    100,   False),  # how often wheel targets are sent
    ("LINK_BAUD",             "link_baud",       921600, int,   9600, 3000000, False), # serial link speed, both boards
    ("CONTROLLER_TIMEOUT",    "controller_timeout", 0.5, float, 0.1,  5.0,   True),   # no telemetry for this long = link lost, s
    ("CLIENT_TIMEOUT",        "client_timeout",  0.5,    float, 0.1,  5.0,   True),   # no drive request for this long = stop, s
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
    """All tunable Wi-Fi board parameters in one object."""

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

    def describe(self):
        """
        Every setting with its value, range and whether it can be changed
        live and was saved, for the web page.
        """
        return {
            attr: {"value": getattr(self, attr), "min": lo, "max": hi,
                   "live": live, "saved": attr in self.saved}
            for _, attr, _, _, lo, hi, live in _FIELDS
        }

    def live_names(self):
        return [f[1] for f in _FIELDS if f[6]]

    def __str__(self):
        return " ".join("{}={}".format(f[1], getattr(self, f[1])) for f in _FIELDS)
