# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Remote control requests: what the web page or a PC script asks the robot
to do, and the safety rules around it.

- Every "drive" request sets the requested v and w. A client that drives
  keeps sending them (the web page does it 20 times a second), so the
  requests double as a heartbeat.
- No request for CLIENT_TIMEOUT seconds (phone locked, out of range,
  browser tab closed): the request goes to v = w = 0 and the robot stops
  with its normal acceleration limits.
- "stop" stops at once and latches: drive requests are refused until the
  client that pressed STOP asks for v = w = 0 (its joystick back in the
  middle), so the robot can't jump off again by itself. Another client
  (a PC script, a second phone) can't end someone else's STOP, unless that
  client has disconnected. A STOP sent over plain HTTP (/api/stop) has no
  client name, so any client can end it.
"""
import time

NS_PER_S = 1_000_000_000
V_LIMIT = 2.0     # m/s, hard limit for a request (the drive's wheel speed limit is lower)
W_LIMIT = 20.0    # rad/s


def _number(value, limit):
    """Return value as a float within +-limit, or None if it isn't a number."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value != value:          # NaN
        return None
    return max(-limit, min(limit, value))


class Remote:
    """
    :param float timeout: Seconds without a drive request after which the robot stops.
    """

    def __init__(self, timeout):
        self.timeout = timeout
        self.v = 0.0
        self.w = 0.0
        self.source = None          # who sent the newest request ("ws1", "http", ...)
        self.latched = False        # True after "stop" until a (0, 0) request
        self.latched_by = []        # the clients that pressed STOP (the page sends it two ways)
        self._last = None           # time.monotonic_ns() of the newest request

    def drive(self, v, w, source):
        """
        Handle a drive request.

        :return str | None: An error message, or None if the request was used.
        """
        v = _number(v, V_LIMIT)
        w = _number(w, W_LIMIT)
        if v is None or w is None:
            return "v and w must be numbers"
        self._last = time.monotonic_ns()
        self.source = source
        if self.latched:
            if self.latched_by and source not in self.latched_by:
                return "held: STOP was pressed on another client ({})".format(self.latched_by[0])
            if v != 0.0 or w != 0.0:
                return "stopped: send v=0, w=0 first"
            self.latched = False
            self.latched_by = []
        self.v = v
        self.w = w
        return None

    def stop(self, source):
        """Emergency stop: zero the request and latch."""
        self.v = 0.0
        self.w = 0.0
        self.latched = True
        # "http" is not one client: if it owned the STOP, a page that sent
        # STOP over HTTP (its WebSocket was down) could never end it
        if source != "http" and source not in self.latched_by:
            self.latched_by.append(source)
        self.source = source
        self._last = time.monotonic_ns()

    def forget(self, source):
        """A client disconnected: its STOP can now be ended by anyone."""
        if source in self.latched_by:
            self.latched_by.remove(source)

    def active(self):
        """True while drive requests keep arriving."""
        if self._last is None:
            return False
        return time.monotonic_ns() - self._last < self.timeout * NS_PER_S

    def command(self):
        """The (v, w) the drive should follow now: the request, or (0, 0) after the timeout."""
        if not self.active():
            self.v = 0.0
            self.w = 0.0
        return self.v, self.w
