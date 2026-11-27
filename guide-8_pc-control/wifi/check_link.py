# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Check the serial link to the controller board. Run with the wheels off the
ground: it spins each wheel slowly and prints OK or FAIL for each check.
"""
import busio

import pins
from config import RobotConfig
from controller import Controller
from link import Link
from ticker import Ticker

TEST_RPM = 30.0      # slow, so a wrong direction is easy to see
SPIN_TIME = 2.0      # seconds per wheel test
START_DELAY = 5      # seconds to step back from the robot


def result(ok, text, fix=""):
    print("{} {}".format("OK  " if ok else "FAIL", text))
    if not ok and fix:
        print("     -> " + fix)
    return ok


def pump(controller, ticker, seconds, left=None, right=None):
    """
    Poll the link for some seconds. With left/right given, also send those
    wheel targets on every pass. Return the mean measured RPM of both wheels
    over the second half of the time.
    """
    elapsed = 0.0
    sum_l = sum_r = 0.0
    count = 0
    while elapsed < seconds:
        controller.poll()
        dt = ticker.due()
        if dt is None:
            continue
        elapsed += dt
        if left is not None:
            controller.send_targets(left, right)
        if elapsed > seconds / 2:
            sum_l += controller.rpm_left
            sum_r += controller.rpm_right
            count += 1
    count = max(count, 1)
    return sum_l / count, sum_r / count


def check_wheel(name, rpm, other_rpm):
    """Check one wheel's measured speed while only it was asked to turn."""
    if abs(other_rpm) > TEST_RPM / 2:
        return result(False, "{} wheel: {:.1f} RPM, but the other wheel turned ({:.1f} RPM)".format(
            name, rpm, other_rpm), "the left and right motors (or encoders) are swapped")
    if rpm < -TEST_RPM / 2:
        return result(False, "{} wheel: {:.1f} RPM, turned backward".format(name, rpm),
                      "if the wheel turned backward, swap its motor wires; if it turned "
                      "forward but counts backward, swap its encoder A/B pins (guide 5)")
    if abs(rpm - TEST_RPM) > 0.3 * TEST_RPM:
        return result(False, "{} wheel: {:.1f} RPM, expected about {:.0f}".format(name, rpm, TEST_RPM),
                      "check that this wheel turned at all, and the other wheel's wiring")
    return result(True, "{} wheel: {:.1f} RPM".format(name, rpm))


def main():
    cfg = RobotConfig()
    uart = busio.UART(pins.LINK_TX, pins.LINK_RX, baudrate=cfg.link_baud,
                      timeout=0, receiver_buffer_size=2048)
    controller = Controller(Link(uart), cfg.controller_timeout)
    ticker = Ticker(cfg.drive_period_ms * 1_000_000)
    all_ok = True

    # 1. Hello and settings
    controller.hello()
    pump(controller, ticker, 2.0)
    if not result(bool(controller.params), "controller board answers ({}), {} settings".format(
            controller.firmware, len(controller.params)),
            "swap TX and RX if the wires are crossed the wrong way; check GND, "
            "LINK_BAUD on both boards, and that the controller's code.py runs"):
        return
    period_ms = controller.param("control_period_ms", 20)
    every = controller.param("telemetry_every", 1)

    # 2. Telemetry rate and damaged frames
    count0 = controller.telemetry_count
    bad0 = controller.link.frames_bad
    pump(controller, ticker, 2.0)
    rate = (controller.telemetry_count - count0) / 2.0
    expected = 1000.0 / (period_ms * every)
    all_ok &= result(abs(rate - expected) < 0.1 * expected,
                     "telemetry {:.1f} frames/s, expected {:.1f}".format(rate, expected),
                     "the controller board's loop runs late: check CONTROL_PERIOD_MS and "
                     "TELEMETRY_EVERY in its settings.toml")
    bad = controller.link.frames_bad - bad0
    all_ok &= result(bad == 0, "damaged frames: {}".format(bad),
                     "check the wires and GND; try LINK_BAUD=460800 on both boards")

    # 3. Wheels, one at a time
    print("Spinning the wheels in {} s: lift the robot!".format(START_DELAY))
    pump(controller, ticker, START_DELAY)     # keep reading the link while waiting
    rpm_l, rpm_r = pump(controller, ticker, SPIN_TIME, TEST_RPM, 0.0)
    all_ok &= check_wheel("left", rpm_l, rpm_r)
    pump(controller, ticker, 1.0, 0.0, 0.0)
    rpm_l, rpm_r = pump(controller, ticker, SPIN_TIME, 0.0, TEST_RPM)
    all_ok &= check_wheel("right", rpm_r, rpm_l)

    # 4. Watchdog: spin both wheels, then stop sending targets
    pump(controller, ticker, 1.0, TEST_RPM, TEST_RPM)
    timeouts0 = controller.timeouts
    link_timeout = controller.param("link_timeout", 0.3)
    rpm_l, rpm_r = pump(controller, ticker, link_timeout + 1.0)
    stopped = controller.timeouts > timeouts0
    all_ok &= result(stopped and abs(controller.target_left) < 1 and abs(controller.target_right) < 1,
                     "controller stopped the motors {:.1f} s after the targets stopped".format(link_timeout),
                     "no timeout event: check LINK_TIMEOUT in the controller's settings.toml")
    all_ok &= result(abs(controller.rpm_left) < 3 and abs(controller.rpm_right) < 3,
                     "wheels at rest: {:.1f} / {:.1f} RPM".format(controller.rpm_left, controller.rpm_right))

    print("All checks passed" if all_ok else "Some checks failed, see above")


main()
