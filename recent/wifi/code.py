# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
RW-1 Wi-Fi board: drive the robot from a phone or a PC over Wi-Fi.
Runs the web server and the kinematics and sends wheel targets to the
controller board. Runs lib/update_self.py instead during a code update.
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
import update_controller
import update_self
import updates
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
    if updates.take():
        update_self.run()         # update mode: never returns, resets when done
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
            net.update(busy=remote.active() or drive.moving())

            # Code update for the controller board, asked for from the web page
            if web.update_now:
                web.update_now = False
                drive.stop()
                try:
                    update_controller.send_files(controller.link, web.pending)
                    web.update_result = {"state": "done", "files": sorted(web.pending)}
                    web.pending = {}
                except update_controller.UpdateError as error:
                    web.update_result = {"state": "error", "error": str(error)}
                print("Controller update:", web.update_result)

            # Restart after a Wi-Fi settings change or for an update (the response was sent already)
            if web.reboot_at is not None and now >= web.reboot_at:
                drive.stop()
                print("Restarting")
                time.sleep(0.2)
                microcontroller.reset()
    finally:
        drive.stop()


main()
