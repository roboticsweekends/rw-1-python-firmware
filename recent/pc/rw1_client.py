# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Talk to the RW-1 robot from a PC: the same API the web page uses.

Plain Python 3.8+ on Windows, macOS or Linux, standard library only (no
pip packages). Copy this file next to your own script and import it:

    from rw1_client import Robot

    robot = Robot("rw-1.local")          # or "192.168.4.1", or the robot's IP
    print(robot.info()["limits"])        # the fastest v and w
    robot.connect()                      # live connection (WebSocket)
    robot.drive(0.2, 0.0)                # 0.2 m/s forward...
    ...                                  # ...repeat at least every 0.5 s
    print(robot.sample)                  # newest telemetry as a dict
    robot.stop()
    robot.close()

Driving needs a stream of requests: the robot stops by itself when no
request arrives for CLIENT_TIMEOUT (0.5 s), so a crashed script can't leave
it running. Robot.drive_for() does the repeating for you.
"""
import base64
import json
import os
import socket
import struct
import threading
import time
import urllib.error
import urllib.request

DRIVE_PERIOD_S = 0.05      # 20 requests a second while driving


class RobotError(Exception):
    """The robot refused a request (the text says why)."""


class Robot:
    """
    One robot. HTTP calls work on their own; drive() and the telemetry need
    connect() first.
    """

    def __init__(self, host="rw-1.local", port=80, timeout=5.0):
        if ":" in host:                      # "192.168.4.1:8080" also works
            host, port = host.rsplit(":", 1)
        self.host = host
        self.port = int(port)
        self.timeout = timeout
        self.fields = []           # telemetry column names, from the robot
        self.sample = None         # newest telemetry sample as a dict
        self.state = {}            # newest "state" message (driver, latched, ...)
        self.on_samples = None     # optional function(list of dicts), called for every batch
        self.errors = []           # error texts the robot sent back
        self._sock = None
        self._reader = None
        self._send_lock = threading.Lock()
        self._last_ping = 0.0

    # --- HTTP (JSON) -----------------------------------------------------

    def _http(self, path, body=None):
        url = "http://{}:{}{}".format(self.host, self.port, path)
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(url, data=data, method="GET" if body is None else "POST",
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as reply:
                return json.loads(reply.read() or b"{}")
        except urllib.error.HTTPError as error:
            try:
                text = json.loads(error.read()).get("error", str(error))
            except ValueError:
                text = str(error)
            raise RobotError(text) from None

    def info(self):
        """Name, Wi-Fi, controller link and speed limits."""
        return self._http("/api/info")

    def telemetry(self):
        """The newest telemetry sample, without a live connection."""
        return self._http("/api/telemetry")

    def params(self):
        """Settings of both boards: {"wifi_board": {...}, "controller": {...}}."""
        return self._http("/api/params")

    def set_params(self, wifi_board=None, controller=None):
        """Change live settings, e.g. set_params(wifi_board={"max_accel": 1.0})."""
        body = {}
        if wifi_board:
            body["wifi_board"] = wifi_board
        if controller:
            body["controller"] = controller
        return self._http("/api/params", body)

    def save_params(self, board="both"):
        """Keep the applied settings after a restart: "wifi_board", "controller" or "both"."""
        return self._http("/api/params/save", {"board": board})

    def reset_params(self, board="both"):
        """Back to the values in settings.toml."""
        return self._http("/api/params/reset", {"board": board})

    def wheel_settings(self):
        """(wheel diameter m, track width m, encoder counts per revolution)."""
        p = self.params()
        return (p["wifi_board"]["wheel_diameter"]["value"],
                p["wifi_board"]["track_width"]["value"],
                p["controller"]["values"]["ticks_per_rev"])

    # --- live connection (WebSocket) --------------------------------------

    def connect(self):
        """Open the live connection and wait for the robot's hello."""
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall(("GET /ws HTTP/1.1\r\nHost: {}\r\nUpgrade: websocket\r\n"
                      "Connection: Upgrade\r\nSec-WebSocket-Key: {}\r\n"
                      "Sec-WebSocket-Version: 13\r\n\r\n").format(self.host, key).encode())
        reply = b""
        while b"\r\n\r\n" not in reply:
            chunk = sock.recv(1024)
            if not chunk:
                raise RobotError("the robot closed the connection")
            reply += chunk
        if b" 101 " not in reply.split(b"\r\n")[0]:
            raise RobotError("no WebSocket: " + reply.split(b"\r\n")[0].decode(errors="replace"))
        self._buffer = reply.split(b"\r\n\r\n", 1)[1]
        sock.settimeout(None)
        self._sock = sock
        self._hello = threading.Event()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        if not self._hello.wait(self.timeout):
            raise RobotError("no hello from the robot")
        return self

    def close(self):
        if self._sock:
            try:
                self._send_frame(0x8, b"")           # close frame
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        """Leaving a "with Robot(...).connect() as robot:" block stops the robot."""
        try:
            if self._sock:
                self.stop()
        except (RobotError, OSError):
            pass
        finally:
            self.close()

    def send(self, message):
        """Send one JSON message ({"t": "drive", ...}) over the live connection."""
        if not self._sock:
            raise RobotError("the connection to the robot was lost" if self._reader
                             else "call connect() first")
        self._send_frame(0x1, json.dumps(message).encode())

    def drive(self, v, w):
        """One drive request: v in m/s (forward +), w in rad/s (left +)."""
        self.send({"t": "drive", "v": round(v, 4), "w": round(w, 4)})

    def stop(self):
        """Stop at once. The robot then waits for drive(0, 0) before it moves again."""
        self.send({"t": "stop"})
        time.sleep(0.05)
        self.drive(0, 0)

    def drive_for(self, v, w, seconds):
        """Drive at v, w for some seconds, repeating the request; then ask for 0."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.drive(v, w)
            time.sleep(DRIVE_PERIOD_S)
        self.drive(0, 0)

    def keep_alive(self):
        """Call now and then while not driving: the robot drops a silent client after 10 s."""
        if time.monotonic() - self._last_ping > 2:
            self._last_ping = time.monotonic()
            self.send({"t": "ping"})

    # --- WebSocket frames (RFC 6455, just what the robot uses) ---------------

    def _send_frame(self, opcode, payload):
        header = bytearray([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header += struct.pack("!BH", 0x80 | 126, n)
        else:
            header += struct.pack("!BQ", 0x80 | 127, n)
        mask = os.urandom(4)                    # clients must mask their frames
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        with self._send_lock:
            self._sock.sendall(bytes(header) + mask + masked)

    def _recv_exact(self, n):
        while len(self._buffer) < n:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("closed")
            self._buffer += chunk
        data, self._buffer = self._buffer[:n], self._buffer[n:]
        return data

    def _read_loop(self):
        try:
            while True:
                b0, b1 = self._recv_exact(2)
                n = b1 & 0x7F
                if n == 126:
                    n = struct.unpack("!H", self._recv_exact(2))[0]
                elif n == 127:
                    n = struct.unpack("!Q", self._recv_exact(8))[0]
                payload = self._recv_exact(n)
                opcode = b0 & 0x0F
                if opcode == 0x8:               # close
                    break
                if opcode == 0x9:               # ping -> pong
                    self._send_frame(0xA, payload)
                elif opcode == 0x1:
                    self._on_message(json.loads(payload))
        except (OSError, ConnectionError, ValueError):
            pass
        self._sock = None

    def _on_message(self, m):
        kind = m.get("t")
        if kind == "hello":
            self.fields = m["fields"]
            self.limits = m["limits"]
            self._hello.set()
        elif kind == "tel":
            samples = [dict(zip(self.fields, s)) for s in m["s"]]
            if samples:
                self.sample = samples[-1]
                if self.on_samples:
                    self.on_samples(samples)
        elif kind == "state":
            self.state = m
        elif kind == "error":
            self.errors.append(m.get("text", ""))
