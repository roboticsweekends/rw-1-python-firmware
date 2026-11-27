# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Send uploaded code files to the controller board over the serial link.
"""
import struct
import time

import link
import updates

CHUNK = 240              # data bytes per FILE frame
RESTART_TIMEOUT_S = 15   # the controller board restarting into its updater
REPLY_TIMEOUT_S = 3      # waiting for an answer to a command
ACK_TIMEOUT_S = 0.25     # waiting for one part's ack, before sending it again
RETRIES = 8


class UpdateError(Exception):
    pass


def _ask(lnk, message, answers, seconds, tries=3):
    """
    Send a TEXT command and wait for one of the answers (cmd names); send it
    again if no answer comes, in case it was damaged on the way.
    Return the answer's pairs.
    """
    for _ in range(tries):
        lnk.send_text(message)
        end = time.monotonic() + seconds / tries
        while time.monotonic() < end:
            frame = lnk.poll()
            if frame is None or frame[0] != link.TEXT:
                continue
            pairs = link.unpack_text(frame[1])
            if pairs.get("cmd") in answers:
                return pairs
            if pairs.get("cmd") == "update_error":
                raise UpdateError(pairs.get("error", "error"))
    raise UpdateError("no answer from the controller board ({})".format(message["cmd"]))


def _wait_ack(lnk, seq):
    end = time.monotonic() + ACK_TIMEOUT_S
    while time.monotonic() < end:
        frame = lnk.poll()
        if frame is None:
            continue
        if frame[0] == link.FILE and len(frame[1]) == 2:
            if struct.unpack("<H", frame[1])[0] == seq:
                return True
        elif frame[0] == link.TEXT:
            pairs = link.unpack_text(frame[1])
            if pairs.get("cmd") == "update_error":
                raise UpdateError(pairs.get("error", "error"))
    return False


def _send_file(lnk, name, data, progress):
    _ask(lnk, {"cmd": "file", "name": name, "size": len(data), "sum": updates.adler32(data)},
         ("file_ready",), REPLY_TIMEOUT_S)
    seq = 0
    for start in range(0, len(data), CHUNK):
        part = data[start:start + CHUNK]
        payload = struct.pack("<HI", seq, updates.adler32(part)) + part
        for _ in range(RETRIES):
            lnk.send(link.FILE, payload)
            if _wait_ack(lnk, seq):
                break
        else:
            raise UpdateError("no ack for part {} of {}".format(seq, name))
        seq += 1
        progress(name, start + CHUNK)
    _ask(lnk, {"cmd": "end"}, ("file_ok",), REPLY_TIMEOUT_S)


def send_files(lnk, files, progress=lambda name, done: None):
    """
    Update the controller board with files: {name: bytes}. Blocks until it
    is done (or raises UpdateError); the controller board then restarts
    with the new code.
    """
    _ask(lnk, {"cmd": "update"}, ("updater",), RESTART_TIMEOUT_S, tries=5)
    try:
        for name in sorted(files):
            print("Sending", name, len(files[name]), "bytes")
            for attempt in range(3):
                try:
                    _send_file(lnk, name, files[name], progress)
                    break
                except UpdateError as error:
                    # A damaged frame got through: send the whole file again
                    if str(error) not in ("bad_sum", "bad_size") or attempt == 2:
                        raise
                    print("Sending", name, "again:", error)
        # After the commit the controller board restarts with the new code:
        # its "hello" also means done, in case the "update_done" got lost
        _ask(lnk, {"cmd": "commit"}, ("update_done", "hello"), RESTART_TIMEOUT_S)
    except UpdateError:
        lnk.send_text({"cmd": "abort"})
        raise
