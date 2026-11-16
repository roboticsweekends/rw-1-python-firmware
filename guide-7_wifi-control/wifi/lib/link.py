# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
The serial link between the controller board and the Wi-Fi board.

The same file is used on both boards.

Every message travels as one frame:

    0xA5 | type | length | payload (length bytes) | checksum

  0xA5     - start byte: marks where a frame begins
  type     - what the payload is (TARGETS, TELEMETRY, STOP, TEXT)
  length   - payload size in bytes, 0..255
  checksum - (type + length + sum of the payload bytes) & 0xFF

The two messages sent on every control pass, wheel targets and telemetry,
are packed as binary numbers with ``struct``: they are short (8 and 25 bytes
per frame) and cost one call to pack or unpack. Rare messages (parameters,
events) are TEXT frames with readable "key=value" pairs.

A receiver that gets out of step (a lost or damaged byte) skips bytes until
the next 0xA5 that starts a frame with a correct checksum.
"""
import struct

START = 0xA5
MAX_PAYLOAD = 255

# Frame types. The values are the ASCII codes of the letters in the comments,
# so they are easy to spot in a byte dump.
TARGETS = 0x57     # "W": wheel targets, Wi-Fi board -> controller board
TELEMETRY = 0x54   # "T": one control pass, controller board -> Wi-Fi board
STOP = 0x58        # "X": stop the motors now, Wi-Fi board -> controller board
TEXT = 0x43        # "C": "key=value key=value" text, both directions
FILE = 0x46        # "F": reserved for code updates over the link

# Payload layouts ("<" = little-endian, h = int16, H = uint16, i = int32)
# TARGETS: left and right wheel target in 0.01 RPM
TARGETS_FORMAT = "<hh"
# TELEMETRY: time in ms (wraps every 65.5 s), left and right encoder counts,
# measured RPM, target RPM (0.01 RPM), motor duty (0.01 %)
TELEMETRY_FORMAT = "<Hiihhhhhh"

# Payload length of each frame type. TEXT and FILE frames can be any length.
# A frame whose length doesn't match its type is dropped at once, so a
# damaged length byte doesn't make the receiver wait for bytes that belong
# to the next frames.
FIXED_LENGTH = {
    TARGETS: struct.calcsize(TARGETS_FORMAT),       # 4
    TELEMETRY: struct.calcsize(TELEMETRY_FORMAT),   # 22
    STOP: 0,
}
KNOWN_TYPES = (TARGETS, TELEMETRY, STOP, TEXT, FILE)

INT16_MAX = 32767


def _int16(value):
    """Round to an int and clamp to the int16 range, so struct.pack can't fail."""
    value = int(round(value))
    if value > INT16_MAX:
        return INT16_MAX
    if value < -INT16_MAX:
        return -INT16_MAX
    return value


def checksum(ftype, payload):
    """Checksum of a frame: the low byte of the sum of type, length and payload."""
    return (ftype + len(payload) + sum(payload)) & 0xFF


def make_frame(ftype, payload=b""):
    """Build the bytes of one frame. The payload must be 255 bytes or shorter."""
    return (bytes((START, ftype, len(payload))) + payload
            + bytes((checksum(ftype, payload),)))


def pack_targets(left_rpm, right_rpm):
    return struct.pack(TARGETS_FORMAT, _int16(left_rpm * 100), _int16(right_rpm * 100))


def unpack_targets(payload):
    """:return tuple: (left RPM, right RPM)"""
    left, right = struct.unpack(TARGETS_FORMAT, payload)
    return left / 100, right / 100


def pack_telemetry(ms, pos_left, pos_right, rpm_left, rpm_right,
                   target_left, target_right, duty_left, duty_right):
    """duty_left and duty_right are in percent of full PWM, -100 .. 100."""
    return struct.pack(
        TELEMETRY_FORMAT,
        ms & 0xFFFF,
        pos_left, pos_right,
        _int16(rpm_left * 100), _int16(rpm_right * 100),
        _int16(target_left * 100), _int16(target_right * 100),
        _int16(duty_left * 100), _int16(duty_right * 100),
    )


def unpack_telemetry(payload):
    """
    :return tuple: (ms, pos_left, pos_right, rpm_left, rpm_right,
                    target_left, target_right, duty_left, duty_right),
                   RPM in RPM and duty in percent.
    """
    v = struct.unpack(TELEMETRY_FORMAT, payload)
    return (v[0], v[1], v[2],
            v[3] / 100, v[4] / 100, v[5] / 100, v[6] / 100,
            v[7] / 100, v[8] / 100)


def ms_since(new_ms, old_ms):
    """Milliseconds between two 16-bit telemetry times, across the wrap."""
    return (new_ms - old_ms) & 0xFFFF


def pack_text(pairs):
    """
    Turn a dict into "key=value key=value" bytes. Keys and values must not
    contain spaces or "=".
    """
    return " ".join("{}={}".format(k, v) for k, v in pairs.items()).encode()


def unpack_text(payload):
    """Turn "key=value key=value" bytes back into a dict of strings."""
    pairs = {}
    for item in payload.decode().split():
        key, _, value = item.partition("=")
        pairs[key] = value
    return pairs


class Link:
    """
    Frame sender and receiver on top of a UART.

    Call ``poll()`` in the main loop until it returns None: each call returns
    one received frame as ``(type, payload)``.

    :param uart: A ``busio.UART`` created with ``timeout=0``, so reads never wait.
    :param int buffer_size: Receive buffer size; must hold at least one full frame.
    """

    def __init__(self, uart, buffer_size=1024):
        self._uart = uart
        self._size = buffer_size
        self._buf = bytearray(buffer_size)
        # Received bytes not yet used are _buf[_start:_end]
        self._start = 0
        self._end = 0
        self.frames_ok = 0     # frames received with a correct checksum
        self.frames_bad = 0    # frames dropped: bad length or checksum
        self.bytes_skipped = 0  # bytes thrown away while looking for a start byte

    # --- sending -----------------------------------------------------------

    def send(self, ftype, payload=b""):
        self._uart.write(make_frame(ftype, payload))

    def send_targets(self, left_rpm, right_rpm):
        self.send(TARGETS, pack_targets(left_rpm, right_rpm))

    def send_stop(self):
        self.send(STOP)

    def send_text(self, pairs):
        """
        Send a dict as "key=value" text. A message longer than one frame is
        split into several frames, each starting with the same "cmd" and all
        but the last carrying "more=1"; the receiver joins them.
        """
        head = "cmd={}".format(pairs.get("cmd", ""))
        items = ["{}={}".format(k, v) for k, v in pairs.items() if k != "cmd"]
        text = head
        for item in items:
            # +8 leaves room for " more=1"
            if len(text) + 1 + len(item) + 8 > MAX_PAYLOAD:
                self.send(TEXT, (text + " more=1").encode())
                text = head
            text += " " + item
        self.send(TEXT, text.encode())

    # --- receiving ---------------------------------------------------------

    def _fill(self):
        """Move the bytes waiting in the UART into our buffer."""
        if self._start == self._end:
            # Everything was used: start again at the front of the buffer
            self._start = self._end = 0
        elif self._end == self._size and self._start > 0:
            # The buffer is full up to the end: move the unused bytes to the front
            rest = self._buf[self._start:self._end]
            self._buf = rest + bytearray(self._size - len(rest))
            self._end = len(rest)
            self._start = 0
        if self._end < self._size and self._uart.in_waiting:
            n = self._uart.readinto(memoryview(self._buf)[self._end:])
            if n:
                self._end += n

    def poll(self):
        """
        Return the next complete frame as (type, payload), or None if there
        isn't one yet.
        """
        self._fill()
        buf = self._buf
        while self._start < self._end:
            s = self._start
            # Skip bytes until a start byte
            if buf[s] != START:
                self._start += 1
                self.bytes_skipped += 1
                continue
            if self._end - s < 3:
                return None               # the header isn't complete yet
            ftype = buf[s + 1]
            length = buf[s + 2]
            if ftype not in KNOWN_TYPES or FIXED_LENGTH.get(ftype, length) != length:
                # Not a frame start (a 0xA5 inside data) or a damaged header
                self.frames_bad += 1
                self._start += 1
                continue
            check_at = s + 3 + length     # index of the checksum byte
            if check_at >= self._end:
                return None               # the rest hasn't arrived yet
            payload = bytes(buf[s + 3:check_at])
            if buf[check_at] != checksum(ftype, payload):
                # Damaged frame, or a 0xA5 inside another frame's data:
                # skip this start byte and look for the next one
                self.frames_bad += 1
                self._start += 1
                continue
            self._start = check_at + 1
            self.frames_ok += 1
            return ftype, payload
        return None
