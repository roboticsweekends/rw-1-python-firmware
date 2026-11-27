# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Settings saved from the web page, kept in the board's NVM as JSON.
The same file is used on both boards.
"""
import json
import struct

try:
    import microcontroller
    _nvm = microcontroller.nvm
except (ImportError, AttributeError):
    _nvm = None

_MAGIC = b"RS"
_HEADER = 4   # magic + length


def _checksum(data):
    return sum(data) & 0xFF


def _load_all():
    """All sections as a dict, or an empty dict if nothing valid is saved."""
    if _nvm is None or bytes(_nvm[0:2]) != _MAGIC:
        return {}
    length = struct.unpack("<H", bytes(_nvm[2:4]))[0]
    if length == 0 or _HEADER + length + 1 > len(_nvm):
        return {}
    data = bytes(_nvm[_HEADER:_HEADER + length])
    if _nvm[_HEADER + length] != _checksum(data):
        return {}
    try:
        values = json.loads(data.decode())
    except ValueError:
        return {}
    return values if isinstance(values, dict) else {}


def _save_all(sections):
    if _nvm is None:
        raise ValueError("no NVM on this board")
    data = json.dumps(sections).encode()
    total = _HEADER + len(data) + 1
    if total > len(_nvm):
        raise ValueError("too much to save: {} bytes, NVM has {}".format(total, len(_nvm)))
    _nvm[0:total] = _MAGIC + struct.pack("<H", len(data)) + data + bytes((_checksum(data),))


def load(section="params"):
    """Return the saved values of one section as a dict (empty if none)."""
    values = _load_all().get(section, {})
    return values if isinstance(values, dict) else {}


def save(values, section="params"):
    """
    Save a dict of values as one section; the other sections stay as they
    are. Writes only if something changed, because each write wears the
    flash a little.

    :raises ValueError: if the values don't fit in the NVM.
    """
    sections = _load_all()
    if sections.get(section) == values:
        return
    sections[section] = values
    _save_all(sections)


def clear(section="params"):
    """Forget the saved values of one section."""
    sections = _load_all()
    if section in sections:
        del sections[section]
        _save_all(sections)
