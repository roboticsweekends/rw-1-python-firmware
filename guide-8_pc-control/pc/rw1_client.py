# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
RW-1 API for PC programs (standard library only): HTTP and WebSocket
client, odometry, encoder-based moves, telemetry recording, robot finder.

    from rw1_client import Robot

    with Robot("rw-1.local").connect() as robot:
        robot.drive_distance(0.5)
        robot.turn_angle(90)
"""
import base64
import csv
import ipaddress
import json
import math
import os
import socket
import struct
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DRIVE_PERIOD_S = 0.05      # 20 requests a second while driving

# Settings of drive_distance() and turn_angle()
V = 0.2            # m/s on the straights
W = 1.2            # rad/s in the turns
V_MIN = 0.03       # slowest speeds near the end, so the robot still gets there
W_MIN = 0.2
BRAKE = 0.7        # brake with 70 % of the robot's acceleration limits
LAG = 0.1          # s: how old the telemetry can be when it arrives
K_HEADING = 3.0    # rad/s of correction per rad of heading error


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
        self._read_sock = sock      # the reader thread's own reference: close() clears _sock
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

    def wait_for_sample(self, timeout=5.0):
        """Wait until the first telemetry sample has arrived; returns it."""
        end = time.monotonic() + timeout
        while self.sample is None:
            if time.monotonic() > end:
                raise RobotError("no telemetry from the robot")
            time.sleep(0.05)
        return self.sample

    def check(self):
        """Raise RobotError if the robot refused a request (e.g. STOP pressed on the web page)."""
        if self.errors:
            raise RobotError("the robot refused: " + self.errors[-1])

    def wait_still(self, seconds=0.4):
        """Ask for 0 for a moment, so the robot comes to rest before the next move."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.drive(0, 0)
            time.sleep(DRIVE_PERIOD_S)

    def drive_distance(self, length, v=V, odo=None):
        """
        Drive straight for `length` metres (negative = backwards), using the
        wheel encoders, and come to rest. Returns (distance m, heading drift rad).
        """
        odo = odo or Odometry(self)
        sign = 1 if length >= 0 else -1
        start = odo.counts()
        while True:
            dist, heading = odo.since(start, LAG)
            left = abs(length) - sign * dist
            if left <= 0:
                break
            self.check()
            speed = max(V_MIN, min(v, math.sqrt(2 * odo.accel * left)))
            self.drive(sign * speed, -K_HEADING * heading)
            time.sleep(DRIVE_PERIOD_S)
        self.wait_still()
        return odo.since(start)

    def turn_angle(self, degrees, w=W, odo=None):
        """
        Turn on the spot by `degrees` (positive = left), using the wheel
        encoders, and come to rest. Returns the angle turned, in degrees.
        """
        odo = odo or Odometry(self)
        angle = math.radians(degrees)
        sign = 1 if angle >= 0 else -1
        start = odo.counts()
        while True:
            _, turned = odo.since(start, LAG)
            left = abs(angle) - sign * turned
            if left <= 0:
                break
            self.check()
            speed = max(W_MIN, min(w, math.sqrt(2 * odo.ang_accel * left)))
            self.drive(0, sign * speed)
            time.sleep(DRIVE_PERIOD_S)
        self.wait_still()
        return math.degrees(odo.since(start)[1])

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
        sock = self._sock
        if sock is None:
            raise OSError("closed")
        with self._send_lock:
            sock.sendall(bytes(header) + mask + masked)

    def _recv_exact(self, n):
        while len(self._buffer) < n:
            chunk = self._read_sock.recv(4096)
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


class Odometry:
    """
    Distance and heading from the encoder counts (the same odometry as guide 6).
    Needs a connected robot that has sent telemetry.
    """

    def __init__(self, robot):
        robot.wait_for_sample()
        diameter, self.track, ticks = robot.wheel_settings()
        self.m_per_tick = math.pi * diameter / ticks
        p = robot.params()["wifi_board"]
        self.accel = BRAKE * p["max_accel"]["value"]           # m/s^2
        self.ang_accel = BRAKE * p["max_ang_accel"]["value"]   # rad/s^2
        self.robot = robot

    def counts(self):
        """The encoder counts now: (left, right). Keep them as a start mark."""
        s = self.robot.sample
        return s["pos_l"], s["pos_r"]

    def since(self, start, ahead=0.0):
        """
        (distance m, turn rad) since the counts in start. With ahead > 0,
        also what the robot drives in the next `ahead` seconds at its
        measured speed (telemetry arrives up to 0.1 s late).
        """
        left, right = self.counts()
        s_l = (left - start[0]) * self.m_per_tick
        s_r = (right - start[1]) * self.m_per_tick
        s = self.robot.sample
        return ((s_l + s_r) / 2 + s["v"] * ahead,
                (s_r - s_l) / self.track + s["w"] * ahead)


class Recorder:
    """
    Collects every telemetry sample of a connected robot, with a time column.

        rec = Recorder(robot)       # starts collecting
        ...
        rec.save("run1.csv")
    """

    def __init__(self, robot):
        self.robot = robot
        self.rows = []
        self._t = 0.0
        self._last_ms = None
        robot.on_samples = self._add

    def _add(self, samples):
        for s in samples:
            # The controller's ms counter wraps at 65536: keep our own time
            if self._last_ms is not None:
                self._t += ((s["ms"] - self._last_ms) % 65536) / 1000
            self._last_ms = s["ms"]
            self.rows.append([round(self._t, 3)] + [s[f] for f in self.robot.fields])

    def save(self, path):
        """Write t_s plus the telemetry fields to a CSV file."""
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["t_s"] + self.robot.fields)
            writer.writerows(self.rows)


# --- finding robots ---------------------------------------------------------

def ask(host, timeout=1.0):
    """The robot's /api/info at host (a dict), or None if no robot answers."""
    try:
        with urllib.request.urlopen("http://{}/api/info".format(host), timeout=timeout) as reply:
            info = json.loads(reply.read())
        return info if "telemetry_fields" in info else None
    except (OSError, ValueError):
        return None


def my_address():
    """This PC's address on the network it uses to reach the outside world."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))      # no packet is sent
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def find_robots(name="rw-1", scan=True, on_scan=None):
    """
    Look for robots: name.local, the access point 192.168.4.1, then (with
    scan=True) every address of this PC's network. Returns a list of
    (host, info) pairs, one per robot; Robot(host) connects to it.
    on_scan(network) is called before a scan starts (it takes a few seconds).
    """
    found = {}
    for host in (name + ".local", "192.168.4.1"):
        info = ask(host, timeout=2.0)
        if info:
            found[info["wifi"]["ap"]["ssid"]] = (host, info)

    me = my_address()
    if scan and me and not me.startswith("192.168.4."):
        net = ipaddress.ip_network(me + "/24", strict=False)
        if on_scan:
            on_scan(net)
        hosts = [str(h) for h in net.hosts() if str(h) != me]
        with ThreadPoolExecutor(max_workers=64) as pool:
            for host, info in zip(hosts, pool.map(ask, hosts)):
                if info and info["wifi"]["ap"]["ssid"] not in found:
                    found[info["wifi"]["ap"]["ssid"]] = (host, info)
    return list(found.values())
