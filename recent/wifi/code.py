# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
RW-1 Wi-Fi board: drive the robot from a phone or a PC over Wi-Fi.

Start-up:
  1. For BOOT_WINDOW_S: press the BOOT button now to forget the Wi-Fi
     settings saved from the web page
  2. Open the serial link to the controller board
  3. Wi-Fi: join the home network (if set up), start the access point
  4. Start the web server: http://192.168.4.1 on the access point

One pass of the loop (it never sleeps):
  Web       - answer one HTTP request, read the WebSocket messages
  Link      - read the controller board's telemetry
  Drive     - every DRIVE_PERIOD_MS: the requested v and w (or 0 after
              CLIENT_TIMEOUT without requests) -> ramp -> kinematics ->
              wheel targets to the controller board
  Report    - telemetry to the WebSocket clients every 100 ms
  Wi-Fi     - watch the home network connection
"""
import time

import busio
import digitalio
import microcontroller
import socketpool
import wifi

import pins
from config import RobotConfig
from controller import Controller
from drive import Drive
from link import Link
from remote import Remote
from ticker import Ticker
from web import WebApp
from wifi_setup import WifiSetup

BOOT_WINDOW_S = 3      # seconds to press BOOT after power-up
HELLO_PERIOD_NS = 1_000_000_000


def boot_button_pressed(seconds):
    """Return True if BOOT is pressed within some seconds after start-up."""
    button = digitalio.DigitalInOut(pins.BUTTON)
    button.switch_to_input(pull=digitalio.Pull.UP)
    print("Press BOOT within {} s to forget the Wi-Fi settings".format(seconds))
    end = time.monotonic() + seconds
    pressed = False
    while time.monotonic() < end and not pressed:
        pressed = not button.value      # the button pulls the pin to GND
        time.sleep(0.02)
    button.deinit()
    return pressed


def main():
    if boot_button_pressed(BOOT_WINDOW_S):
        WifiSetup.forget()
        print("BOOT pressed: saved Wi-Fi settings forgotten")

    cfg = RobotConfig()
    print("RW-1 Wi-Fi board")
    print(cfg)

    uart = busio.UART(pins.LINK_TX, pins.LINK_RX, baudrate=cfg.link_baud,
                      timeout=0, receiver_buffer_size=2048)
    controller = Controller(Link(uart), cfg.controller_timeout)
    controller.hello()
    drive = Drive(cfg, controller)
    remote = Remote(cfg.client_timeout)

    net = WifiSetup()
    net.start()
    pool = socketpool.SocketPool(wifi.radio)
    web = WebApp(pool, cfg, controller, drive, remote, net)
    web.start()
    print("Web server running")

    ticker = Ticker(cfg.drive_period_ms * 1_000_000)
    next_hello = time.monotonic_ns() + HELLO_PERIOD_NS
    try:
        while True:
            # Web
            web.poll()

            # Link
            controller.poll()
            now = time.monotonic_ns()
            if not controller.params and now >= next_hello:
                # The controller board hasn't answered yet: maybe it started later
                controller.hello()
                next_hello = now + HELLO_PERIOD_NS

            # Drive
            dt = ticker.due()
            if dt is not None:
                remote.timeout = cfg.client_timeout
                controller.timeout = cfg.controller_timeout
                v, w = remote.command()
                drive.update(v, w, dt)

            # Report
            web.send_updates()

            # Wi-Fi
            net.update(busy=remote.active())

            # Restart after a Wi-Fi settings change (the response was sent already)
            if web.reboot_at is not None and now >= web.reboot_at:
                drive.stop()
                print("Restarting")
                time.sleep(0.2)
                microcontroller.reset()
    finally:
        drive.stop()


main()
