# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Runs before code.py. Makes the drive writable for CircuitPython only when
a code update was requested (lib/updates.py). Copied over USB once; never
replaced over Wi-Fi.
"""
import microcontroller
import storage

FLAG_UPDATE = 0x55     # the same values as in lib/updates.py
FLAG_RUNNING = 0xAA

address = len(microcontroller.nvm) - 1
if microcontroller.nvm[address] == FLAG_UPDATE:
    microcontroller.nvm[address] = FLAG_RUNNING   # code.py starts the updater
    storage.remount("/", readonly=False)          # the PC sees CIRCUITPY read-only now
