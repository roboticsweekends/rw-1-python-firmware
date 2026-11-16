# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
The controller board, as the Wi-Fi board sees it through the serial link.

Call ``poll()`` on every pass of the main loop: it reads every frame that
arrived and keeps the newest values, so the rest of the code can read
``controller.rpm_left``, ``controller.params`` and so on at any time.
"""
import time

import link

NS_PER_S = 1_000_000_000


class Controller:
    """
    :param lnk: link.Link on the UART wired to the controller board.
    :param float timeout: Seconds without telemetry after which the link counts as lost.
    """

    def __init__(self, lnk, timeout):
        self.link = lnk
        self.timeout = timeout

        # Newest telemetry (see link.unpack_telemetry)
        self.ms = 0
        self.pos_left = 0
        self.pos_right = 0
        self.rpm_left = 0.0
        self.rpm_right = 0.0
        self.target_left = 0.0
        self.target_right = 0.0
        self.duty_left = 0.0
        self.duty_right = 0.0
        self.telemetry_count = 0     # telemetry frames received since boot
        self.on_telemetry = None     # optional function called after each telemetry frame
        self._last_seen = None       # time.monotonic_ns() of the newest telemetry

        # Settings of the controller board, as strings: {"max_rpm": "191.8", ...}
        self.params = {}
        self._params_parts = {}      # a "params" message split over several frames
        self.params_saved = []       # names of the settings saved in its NVM
        self.params_live = []        # names of the settings that can be changed while running
        self.params_errors = ""      # errors from the last "set", "" if none
        self.params_version = 0      # +1 every time new params arrive
        self.firmware = None         # from its "hello"
        self.timeouts = 0            # how many times it stopped on a link timeout

    # --- link state ----------------------------------------------------------

    @property
    def ok(self):
        """True while telemetry keeps arriving."""
        if self._last_seen is None:
            return False
        return time.monotonic_ns() - self._last_seen < self.timeout * NS_PER_S

    def param(self, name, default=None):
        """A controller setting as a float, or default if it isn't known yet."""
        try:
            return float(self.params[name])
        except (KeyError, ValueError):
            return default

    # --- receiving -----------------------------------------------------------

    def poll(self):
        """
        Read every frame that arrived.

        :return int: Number of telemetry frames received in this call.
        """
        received = 0
        while True:
            frame = self.link.poll()
            if frame is None:
                return received
            ftype, payload = frame
            if ftype == link.TELEMETRY:
                (self.ms, self.pos_left, self.pos_right,
                 self.rpm_left, self.rpm_right,
                 self.target_left, self.target_right,
                 self.duty_left, self.duty_right) = link.unpack_telemetry(payload)
                self._last_seen = time.monotonic_ns()
                self.telemetry_count += 1
                received += 1
                if self.on_telemetry:
                    self.on_telemetry()
            elif ftype == link.TEXT:
                self._on_text(link.unpack_text(payload))

    def _on_text(self, pairs):
        cmd = pairs.pop("cmd", "")
        if cmd == "hello":
            # The controller board (re)started: read its settings again
            self.firmware = pairs.get("fw")
            self.request_params()
        elif cmd == "params":
            # Long messages come in parts; all but the last say more=1
            more = pairs.pop("more", None)
            self._params_parts.update(pairs)
            if more:
                return
            pairs = self._params_parts
            self._params_parts = {}
            saved = pairs.pop("saved", "-")
            self.params_saved = [] if saved == "-" else saved.split(",")
            self.params_errors = pairs.pop("errors", "")
            live = pairs.pop("live", "")
            self.params_live = live.split(",") if live else []
            self.params = pairs
            self.params_version += 1
        elif cmd == "event" and pairs.get("name") == "timeout":
            self.timeouts += 1

    # --- sending -------------------------------------------------------------

    def send_targets(self, left_rpm, right_rpm):
        self.link.send_targets(left_rpm, right_rpm)

    def stop(self):
        """Stop the motors now, without the ramp."""
        self.link.send_stop()

    def hello(self):
        """Ask the controller board to introduce itself (its firmware, then its settings)."""
        self.link.send_text({"cmd": "hello"})

    def request_params(self):
        self.link.send_text({"cmd": "get"})

    def set_params(self, values):
        """Change live settings: values is {name: value}. The answer arrives as new params."""
        pairs = {"cmd": "set"}
        pairs.update(values)
        self.link.send_text(pairs)

    def save_params(self):
        self.link.send_text({"cmd": "save"})

    def reset_params(self):
        self.link.send_text({"cmd": "reset"})
