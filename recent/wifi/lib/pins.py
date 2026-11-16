# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
RW-1 pin map for the Wi-Fi board (Waveshare ESP32-S3-Zero).

All scripts import their pins from here, so a wiring change is made in one place.
"""
import board

# Serial link to the controller board on GPIO13 (TX) and GPIO12 (RX):
# these pins sit next to the 5V and GND pins, so all four wires to the
# controller board are side by side. Any free GPIOs work: the ESP32-S3 can
# route its UART to any pin. TX goes to the controller's GP5, RX to its GP4.
LINK_TX = board.IO13
LINK_RX = board.IO12

# BOOT button (GPIO0). Hold it while powering up = ESP32 bootloader, so the
# firmware only reads it after start-up.
BUTTON = board.BUTTON
