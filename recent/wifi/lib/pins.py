# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
RW-1 pin map for the Wi-Fi board (Waveshare ESP32-S3-Zero).

All scripts import their pins from here, so a wiring change is made in one place.
"""
import board

# Serial link to the controller board on GPIO1 (TX) and GPIO2 (RX).
# On the ESP32-S3-Zero these pins follow 5V, GND and 3V3 in one row, so all
# four wires to the controller board are side by side. TX goes to the
# controller's GP5, RX to its GP4.
# Other ESP32-S3 boards: any two free GPIOs work, the ESP32-S3 can route its
# UART to any pin. Pick the two next to the power pins, for example
# board.IO13 (TX) and board.IO12 (RX) on an ESP32-S3 Super Mini.
LINK_TX = board.IO1
LINK_RX = board.IO2

# BOOT button (GPIO0). Hold it while powering up = ESP32 bootloader, so the
# firmware only reads it after start-up.
BUTTON = board.BUTTON
