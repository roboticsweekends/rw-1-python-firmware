# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Fixed-rate loop timer: wakes the control loop every period.

The timing of the main loop in part 5's code.py, packed in a class so that
every script can use it.
"""
import time

NS_PER_S = 1_000_000_000


class Ticker:
    """
    Call ``wait()`` once per loop pass; it sleeps until the next pass is due.

    Times are whole nanoseconds from time.monotonic_ns(). time.monotonic()
    returns a float that loses precision after the board has been on for
    about an hour, too coarse for a 20 ms loop.

    :param int period_ns: Loop period in nanoseconds.
    """

    def __init__(self, period_ns):
        self._period = period_ns
        self.reset()

    def reset(self):
        """
        Start timing from now. Call it after a pause, so the first dt is one
        period and not the whole pause.
        """
        self._last = time.monotonic_ns()
        self._next = self._last + self._period

    def wait(self):
        """
        Sleep until the next pass is due.

        :return float: Seconds since the previous pass (dt).
        """
        time.sleep(max(0, self._next - time.monotonic_ns()) / NS_PER_S)
        now = time.monotonic_ns()
        dt = (now - self._last) / NS_PER_S
        self._last = now
        self._next += self._period
        if self._next < now:
            # This pass ran late: skip the missed passes instead of running
            # them back to back
            self._next = now + self._period
        return dt
