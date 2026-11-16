# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Receive new code files from the Wi-Fi board over the serial link.

code.py runs this instead of the wheel control when boot.py started an
update (see lib/updates.py). The motors stay off the whole time.

The Wi-Fi board leads, one file at a time (TEXT frames are "key=value"):

  this board                       Wi-Fi board
  cmd=updater (every 0.5 s)  ->
                             <-    cmd=file name=lib/wheels.py size=4093 sum=...
  cmd=file_ready             ->
                             <-    FILE frame: number (2 bytes), checksum of the
                                   part (4 bytes), up to 240 bytes of the file
  FILE frame: same number    ->    (an "ack": the next part may come; a damaged
                                   part gets no ack and is sent again)
                                   ... until the whole file is sent
                             <-    cmd=end
  cmd=file_ok                ->    (size and checksum match)
                                   ... the next file
                             <-    cmd=commit
  cmd=update_done            ->    the new files are in place, this board resets

Any problem: cmd=update_error error=<what>. cmd=abort, or nothing from the
Wi-Fi board for TIMEOUT_S, throws the new files away and resets with the
old code.
"""
import os
import struct
import time

import microcontroller

import link
import updates

TIMEOUT_S = 30
HELLO_PERIOD_S = 0.5


def run(lnk):
    """Never returns: the board resets at the end."""
    updates.clean_up()
    print("Update mode: waiting for files from the Wi-Fi board")
    received = []          # names of the checked .new files
    current = None         # the file being written: dict
    last_rx = time.monotonic()
    next_hello = 0
    talking = False

    last_reply = {}        # sent again if the Wi-Fi board repeats a command

    def reply(pairs):
        last_reply.clear()
        last_reply.update(pairs)
        lnk.send_text(pairs)

    def error(code):
        reply({"cmd": "update_error", "error": code})
        print("Update error:", code)

    while time.monotonic() - last_rx < TIMEOUT_S:
        now = time.monotonic()
        if not talking and now >= next_hello:
            next_hello = now + HELLO_PERIOD_S
            lnk.send_text({"cmd": "updater"})

        frame = lnk.poll()
        if frame is None:
            continue
        ftype, payload = frame
        if ftype not in (link.TEXT, link.FILE):
            continue                 # e.g. wheel targets sent before the reset
        last_rx = now
        talking = True

        if ftype == link.FILE and current is not None:
            if len(payload) < 6:
                continue
            seq, part_sum = struct.unpack("<HI", payload[:6])
            data = payload[6:]
            if updates.adler32(data) != part_sum:
                continue                 # damaged on the way: no ack, it comes again
            if seq == current["seq"]:
                current["f"].write(data)
                current["got"] += len(data)
                current["sum"] = updates.adler32(data, current["sum"])
                current["seq"] += 1
            # Acknowledge new and repeated parts (a lost ack makes the
            # Wi-Fi board send a part again)
            if seq < current["seq"]:
                lnk.send(link.FILE, struct.pack("<H", seq))
            continue

        pairs = link.unpack_text(payload)
        cmd = pairs.get("cmd")

        if cmd == "file":
            if current:
                current["f"].close()
                current = None
            name = pairs.get("name", "")
            size = int(pairs.get("size", -1))
            problem = updates.check_name(name)
            if problem is None and not 0 <= size <= updates.MAX_FILE:
                problem = "too_big"
            if problem is None and size + 4096 > updates.free_space():
                problem = "no_space"
            if problem:
                error(problem)
                continue
            try:
                f = open(name + ".new", "wb")
            except OSError:
                error("not_writable")
                continue
            current = {"name": name, "size": size, "want": int(pairs.get("sum", 0)),
                       "f": f, "got": 0, "sum": 1, "seq": 0}
            print("Receiving", name, size, "bytes")
            reply({"cmd": "file_ready", "name": name})

        elif cmd == "end" and current is None:
            lnk.send_text(last_reply)    # the answer got lost: send it again

        elif cmd == "end":
            current["f"].close()
            if current["got"] != current["size"]:
                error("bad_size")
            elif current["sum"] != current["want"]:
                error("bad_sum")
            else:
                received.append(current["name"])
                reply({"cmd": "file_ok", "name": current["name"]})
            current = None

        elif cmd == "commit":
            if current:
                current["f"].close()
            updates.swap_in(received)
            print("Update done:", ", ".join(received))
            lnk.send_text({"cmd": "update_done", "files": len(received)})
            time.sleep(0.1)          # let the last frame go out
            microcontroller.reset()

        elif cmd == "abort":
            break

    # Abort or timeout: keep the old code
    if current:
        current["f"].close()
    updates.clean_up()
    print("Update cancelled, restarting with the old code")
    time.sleep(0.1)
    microcontroller.reset()
