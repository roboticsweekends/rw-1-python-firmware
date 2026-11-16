# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
RW-1 controller board: hold the wheel speeds the Wi-Fi board asks for.

From guide 7 the robot is driven through the Wi-Fi board. It runs the
kinematics from guide 6 and sends left and right wheel targets (RPM) over
the serial link (lib/link.py) on every one of its passes. This board keeps
the wheel speed control from guide 5 (lib/wheels.py) and sends back what it
measured.

One pass of the loop, every CONTROL_PERIOD_MS:

  Read      - take the frames that arrived: wheel targets, stop, settings
  Watchdog  - no targets for LINK_TIMEOUT seconds -> stop the motors
  Control   - measure, compare and correct, drive (lib/wheels.py)
  Report    - send one telemetry frame to the Wi-Fi board

A code update from the web page restarts the board into lib/updater.py
instead (see lib/updates.py and boot.py).
"""
import time

import busio
import microcontroller

import link
import pins
import updater
import updates
from config import RobotConfig
from ticker import Ticker
from wheels import Wheels

FIRMWARE = "guide-8"
NS_PER_MS = 1_000_000


def send_hello(cfg, lnk):
    """Introduce this board. boot=1: boot.py is there, so code updates over Wi-Fi work."""
    lnk.send_text({"cmd": "hello", "fw": FIRMWARE, "period_ms": cfg.control_period_ms,
                   "boot": 1 if updates.exists("boot.py") else 0})


def handle_text(pairs, cfg, wheels, lnk):
    """Answer a TEXT frame from the Wi-Fi board."""
    cmd = pairs.pop("cmd", "")
    if cmd == "hello":
        send_hello(cfg, lnk)
        return
    if cmd == "update":
        # Restart into the updater (boot.py makes the drive writable)
        wheels.stop()
        print("Code update: restarting into the updater")
        updates.request()
        time.sleep(0.05)
        microcontroller.reset()

    reply = {"cmd": "params"}
    if cmd == "set":
        errors = []
        for name, text in pairs.items():
            error = cfg.set(name, text)
            if error:
                errors.append("{}:{}".format(name, error))
        wheels.apply_settings()
        if errors:
            reply["errors"] = ",".join(errors)
    elif cmd == "save":
        try:
            cfg.save()
        except ValueError:
            reply["errors"] = "save:failed"
    elif cmd == "reset":
        cfg.reset()
        wheels.apply_settings()
    elif cmd != "get":
        lnk.send_text({"cmd": "error", "unknown": cmd or "none"})
        return
    # "get", and the answer to "set", "save" and "reset": all settings
    reply.update(cfg.to_pairs())
    reply["saved"] = ",".join(cfg.saved) or "-"
    reply["live"] = ",".join(cfg.live_names())
    lnk.send_text(reply)


def main():
    cfg = RobotConfig()
    print("RW-1 controller board,", FIRMWARE)
    print(cfg)
    if cfg.saved:
        print("Saved from the web page:", ", ".join(cfg.saved))

    uart = busio.UART(pins.LINK_TX, pins.LINK_RX, baudrate=cfg.link_baud,
                      timeout=0, receiver_buffer_size=1024)
    lnk = link.Link(uart)
    if updates.take():
        updater.run(lnk)          # never returns: resets when done
    wheels = Wheels(cfg)
    ticker = Ticker(cfg.control_period_ms * NS_PER_MS)

    # Tell the Wi-Fi board we (re)started, so it reads our settings again
    send_hello(cfg, lnk)

    last_targets = time.monotonic_ns()
    stopped = True            # no targets yet: motors off
    passes = 0

    try:
        while True:
            dt = ticker.wait()
            start = time.monotonic_ns()

            # Read: every frame that arrived since the last pass
            while True:
                frame = lnk.poll()
                if frame is None:
                    break
                ftype, payload = frame
                if ftype == link.TARGETS:
                    left, right = link.unpack_targets(payload)
                    wheels.set_targets(left, right)
                    last_targets = start
                    stopped = False
                elif ftype == link.STOP:
                    wheels.stop()
                    stopped = True
                elif ftype == link.TEXT:
                    handle_text(link.unpack_text(payload), cfg, wheels, lnk)

            # Watchdog: the Wi-Fi board went quiet, stop the motors
            if not stopped and start - last_targets > cfg.link_timeout * 1e9:
                wheels.stop()
                stopped = True
                lnk.send_text({"cmd": "event", "name": "timeout"})
                print("Link timeout: motors stopped")

            # Control: measure, compare and correct, drive
            wheels.update(dt)

            # Report
            passes += 1
            if passes >= cfg.telemetry_every:
                passes = 0
                duty_left, duty_right = wheels.duty_percent()
                lnk.send(link.TELEMETRY, link.pack_telemetry(
                    start // NS_PER_MS,
                    wheels.encoders.position_left, wheels.encoders.position_right,
                    wheels.rpm_left, wheels.rpm_right,
                    wheels.target_left, wheels.target_right,
                    duty_left, duty_right))

    finally:
        wheels.stop()


main()
