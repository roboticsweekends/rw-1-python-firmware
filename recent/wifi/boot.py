# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Runs once after power-up or a reset, before code.py.

Normally it does nothing: the CIRCUITPY drive stays writable from the PC.
When code.py asked for a code update (lib/updates.py), it makes the drive
writable for CircuitPython instead, for this one start only.

Copy it to the board over USB once. It is never replaced over Wi-Fi, so
it is always there to get the board back to normal. If something still
goes wrong: double-press the reset button for safe mode, which skips
boot.py and code.py.
"""
import microcontroller
import storage

FLAG_UPDATE = 0x55     # the same values as in lib/updates.py
FLAG_RUNNING = 0xAA

address = len(microcontroller.nvm) - 1
if microcontroller.nvm[address] == FLAG_UPDATE:
    microcontroller.nvm[address] = FLAG_RUNNING   # code.py starts the updater
    storage.remount("/", readonly=False)          # the PC sees CIRCUITPY read-only now
