# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Code updates from the web page: the parts both boards share.

The same file is used on both boards.

CircuitPython can only write to its own drive after boot.py remounted it,
and boot.py only runs after a hard reset. So an update goes like this:

  1. code.py sets the update flag (one byte of microcontroller.nvm) and
     resets the board.
  2. boot.py sees the flag, sets it to "running" and makes the drive
     writable for CircuitPython (the PC then sees it read-only).
  3. code.py sees "running", clears the flag and starts the updater
     instead of the normal program. The next reset is a normal start again.
  4. The updater writes every new file as <name>.new and checks its size
     and checksum. Only when all files are good, swap_in() puts them in
     place, and the board resets.

The flag lives in the last byte of the NVM; lib/store.py uses the start.
"""
import os

try:
    import microcontroller
    _nvm = microcontroller.nvm
except (ImportError, AttributeError):
    _nvm = None

FLAG_UPDATE = 0x55     # code.py asks boot.py for an update start
FLAG_RUNNING = 0xAA    # boot.py made the drive writable: run the updater
MAX_FILE = 65536       # bytes, the largest file an update takes

# Where update files may go, and which names are never replaced over Wi-Fi:
# boot.py is the way back if an update goes wrong.
FOLDERS = ("", "lib/", "www/")
EXTENSIONS = (".py", ".toml", ".html", ".txt", ".json")
PROTECTED = ("boot.py",)


def _flag_address():
    return len(_nvm) - 1


def request():
    """Ask for an update start at the next reset."""
    _nvm[_flag_address()] = FLAG_UPDATE


def take():
    """True if boot.py started an update; clears the flag either way."""
    if _nvm is None:
        return False
    flag = _nvm[_flag_address()]
    if flag in (FLAG_UPDATE, FLAG_RUNNING):
        _nvm[_flag_address()] = 0
    return flag == FLAG_RUNNING


def check_name(name):
    """None if an update may write this file, else the reason why not."""
    folder, _, base = name.rpartition("/")
    folder = folder + "/" if folder else ""
    if folder not in FOLDERS:
        return "bad_folder"
    if not base or base.startswith(".") or not base.endswith(EXTENSIONS):
        return "bad_name"
    for c in base:
        if not (c.isalpha() or c.isdigit() or c in "_-."):
            return "bad_name"
    if name in PROTECTED:
        return "protected"
    return None


def adler32(data, value=1):
    """Adler-32 checksum of data, continuing from value (pass the last result)."""
    a = value & 0xFFFF
    b = value >> 16
    for start in range(0, len(data), 4096):   # keep the sums small between the "%"
        for x in data[start:start + 4096]:
            a += x
            b += a
        a %= 65521
        b %= 65521
    return (b << 16) | a


def exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def free_space():
    """Free bytes on the drive."""
    s = os.statvfs("/")
    return s[0] * s[3]


def swap_in(names):
    """
    Put the checked <name>.new files in place. The old file is kept as
    <name>.old until the new one is in place, then removed.
    """
    for name in names:
        if exists(name):
            if exists(name + ".old"):
                os.remove(name + ".old")
            os.rename(name, name + ".old")
        os.rename(name + ".new", name)
    for name in names:
        if exists(name + ".old"):
            os.remove(name + ".old")


def clean_up():
    """
    Tidy up after an interrupted update: remove *.new files, and put back
    an <name>.old whose new file never arrived.
    """
    for folder in FOLDERS:
        path = folder.rstrip("/") or "."
        try:
            entries = os.listdir(path)
        except OSError:
            continue
        for entry in entries:
            full = folder + entry
            if entry.endswith(".new"):
                os.remove(full)
            elif entry.endswith(".old"):
                if exists(full[:-4]):
                    os.remove(full)
                else:
                    os.rename(full, full[:-4])
