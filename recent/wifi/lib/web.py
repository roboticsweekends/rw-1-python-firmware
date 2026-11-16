# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
The robot's web server: the web page, the JSON API and the WebSocket.

The same API is used by the web page and by programs on the PC.

HTTP (JSON in and out):

  GET  /                    the web page (www/index.html)
  GET  /api/info            robot name, firmware, Wi-Fi, controller link, speed limits
  GET  /api/telemetry       newest telemetry sample
  POST /api/drive           {"v": m/s, "w": rad/s}: same rules as the WebSocket "drive"
  POST /api/stop            stop at once (latched until a v=0, w=0 request; from any client, as HTTP has no client name)
  GET  /api/params          settings of both boards
  POST /api/params          {"wifi_board": {name: value}, "controller": {name: value}}
  POST /api/params/save     {"board": "wifi_board" | "controller" | "both"}
  POST /api/params/reset    same; back to settings.toml
  GET  /api/wifi            Wi-Fi state
  POST /api/wifi/scan       networks in range (only while the robot isn't driven)
  POST /api/wifi/test       {"ssid", "password"}: try a home network without saving it
  POST /api/wifi/client     {"ssid", "password"}: save the home network and restart
  POST /api/wifi/ap         {"ssid", "password"}: save the access point and restart
  POST /api/wifi/name       {"name"}: save the robot's name and restart
  POST /api/wifi/reconnect  try the home network again now
  POST /api/wifi/forget     forget the saved Wi-Fi settings and restart

WebSocket /ws (JSON text messages):

  to the robot:   {"t": "drive", "v": 0.2, "w": 0.0}   send 10-20 times a second while driving
                  {"t": "stop"}
                  {"t": "ping"}                         keeps an idle connection open
  from the robot: {"t": "hello", "fields": [...], ...}  once, after connecting
                  {"t": "tel", "s": [[...], ...]}       telemetry, every 100 ms (5 samples)
                  {"t": "state", ...}                   once a second
                  {"t": "pong"}, {"t": "error", "text": "..."}

A client that sends nothing for CLIENT_IDLE_S seconds is disconnected.
"""
import errno
import json
import time

from adafruit_httpserver import (
    BAD_REQUEST_400,
    GET,
    POST,
    FileResponse,
    JSONResponse,
    Server,
    Websocket,
)

FIRMWARE = "guide-7"
WWW = "/www"
MAX_CLIENTS = 2             # WebSocket connections at once
CLIENT_IDLE_S = 10          # disconnect a WebSocket client silent for this long
TELEMETRY_PERIOD_S = 0.1    # how often telemetry is sent to WebSocket clients
STATE_PERIOD_S = 1.0
SEND_TIMEOUT_NS = 50_000_000  # give up sending to a client after 50 ms
NS_PER_S = 1_000_000_000

# Telemetry sample columns, in this order
TELEMETRY_FIELDS = (
    "ms",                     # controller board time, ms (wraps at 65536)
    "v_cmd", "w_cmd",         # commanded body speed after the ramp, m/s and rad/s
    "v", "w",                 # measured body speed (forward kinematics)
    "target_l", "target_r",   # wheel targets, RPM
    "rpm_l", "rpm_r",         # measured wheel speeds, RPM
    "duty_l", "duty_r",       # motor duty, % of full PWM
    "pos_l", "pos_r",         # encoder counts
)


class RobotWebsocket(Websocket):
    """
    A Websocket that gives up on a client that stops reading (out of range,
    phone locked) instead of waiting for it, so the robot's loop never stalls.

    It replaces the library's _send_bytes() (checked against
    adafruit_httpserver 4.8.0), which retries forever while the client's
    receive buffer is full.
    """

    stalled = False

    def _send_bytes(self, conn, buffer):
        sent = 0
        view = memoryview(buffer)
        start = time.monotonic_ns()
        while sent < len(buffer):
            try:
                sent += conn.send(view[sent:])
            except OSError as error:
                if error.errno == errno.ECONNRESET:   # the client has gone
                    return
                if error.errno != errno.EAGAIN:       # EAGAIN: the send buffer is full
                    raise
                if time.monotonic_ns() - start > SEND_TIMEOUT_NS:
                    self.stalled = True
                    raise BrokenPipeError("client not reading")
        self._size += sent


class Client:
    """One WebSocket connection."""

    count = 0

    def __init__(self, ws):
        Client.count += 1
        self.name = "ws{}".format(Client.count)
        self.ws = ws
        self.greeted = False
        self.last_rx = time.monotonic_ns()


def _bad(request, text):
    return JSONResponse(request, {"ok": False, "error": text}, status=BAD_REQUEST_400)


def _body(request):
    """The request's JSON body as a dict ({} if it's empty or invalid)."""
    try:
        data = request.json()
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


class WebApp:
    """
    :param pool: socketpool.SocketPool for the Wi-Fi radio.
    :param cfg: The Wi-Fi board's RobotConfig.
    :param controller: controller.Controller.
    :param drive: drive.Drive.
    :param remote: remote.Remote.
    :param wifi: wifi_setup.WifiSetup.
    """

    def __init__(self, pool, cfg, controller, drive, remote, wifi):
        self.cfg = cfg
        self.controller = controller
        self.drive = drive
        self.remote = remote
        self.wifi = wifi
        self.clients = []
        self.samples = []            # telemetry not sent yet
        self.latest = None           # newest telemetry sample
        self.reboot_at = None        # time.monotonic_ns() to restart at, after a Wi-Fi change
        self._start_ns = time.monotonic_ns()
        self._next_tel = 0
        self._next_state = 0

        self.server = Server(pool, WWW, debug=False)
        # Short: while a request is read, no wheel targets go out, and the
        # controller board stops the motors after LINK_TIMEOUT (0.3 s)
        self.server.socket_timeout = 0.1
        self._add_routes()
        controller.on_telemetry = self._on_telemetry

    def start(self, port=80):
        # 0.0.0.0: answer on both the access point and the home network
        self.server.start("0.0.0.0", port)

    # --- main loop -------------------------------------------------------

    def poll(self):
        """Handle one HTTP request (if any) and all WebSocket messages."""
        try:
            self.server.poll()
        except Exception as error:   # a bad request must never stop the robot's loop
            print("HTTP error:", repr(error))
        for client in list(self.clients):
            self._poll_client(client)

    def send_updates(self):
        """Send telemetry and state to the WebSocket clients when they're due."""
        now = time.monotonic_ns()
        if now >= self._next_tel:
            self._next_tel = now + int(TELEMETRY_PERIOD_S * NS_PER_S)
            if self.samples:
                self._broadcast({"t": "tel", "s": self.samples})
                self.samples = []
        if now >= self._next_state:
            self._next_state = now + int(STATE_PERIOD_S * NS_PER_S)
            if self.clients:
                self._broadcast(self.state())

    # --- telemetry ---------------------------------------------------------

    def _on_telemetry(self):
        """Called by the controller link for every telemetry frame."""
        c = self.controller
        d = self.drive
        v, w = d.kin.body_speed(c.rpm_left, c.rpm_right)
        sample = [
            c.ms,
            round(d.v_cmd * d.scale, 4), round(d.w_cmd * d.scale, 4),
            round(v, 4), round(w, 4),
            round(c.target_left, 2), round(c.target_right, 2),
            round(c.rpm_left, 2), round(c.rpm_right, 2),
            round(c.duty_left, 2), round(c.duty_right, 2),
            c.pos_left, c.pos_right,
        ]
        self.latest = sample
        if self.clients:
            self.samples.append(sample)
            if len(self.samples) > 50:      # nobody reading: keep the newest second
                self.samples.pop(0)

    # --- state for the page ------------------------------------------------

    def info(self):
        v_max, w_max = self.drive.limits()
        return {
            "name": self.wifi.name,
            "firmware": FIRMWARE,
            "uptime_s": (time.monotonic_ns() - self._start_ns) // NS_PER_S,
            "wifi": self.wifi.info(),
            "controller": {
                "ok": self.controller.ok,
                "firmware": self.controller.firmware,
                "timeouts": self.controller.timeouts,
            },
            "limits": {"v_max": round(v_max, 3), "w_max": round(w_max, 3)},
            "telemetry_fields": TELEMETRY_FIELDS,
            "clients": len(self.clients),
        }

    def state(self):
        r = self.remote
        return {
            "t": "state",
            "controller_ok": self.controller.ok,
            "driver": r.source if r.active() else None,
            "latched": r.latched,
            "wifi": self.wifi.client_state,
            "ip": self.wifi.ip_client(),
            "timeouts": self.controller.timeouts,
            "clients": len(self.clients),
        }

    def params(self):
        c = self.controller
        values = {}
        for name, text in c.params.items():
            try:
                values[name] = float(text) if "." in text else int(text)
            except ValueError:
                values[name] = text
        return {
            "wifi_board": self.cfg.describe(),
            "controller": {
                "values": values,
                "live": c.params_live,
                "saved": c.params_saved,
                "errors": c.params_errors,
            },
        }

    # --- WebSocket clients -------------------------------------------------

    def _add_client(self, ws):
        if len(self.clients) >= MAX_CLIENTS:
            oldest = self.clients.pop(0)
            self._send(oldest, {"t": "error", "text": "another client connected"})
            self._drop(oldest)   # closes it; anyone can now end its STOP
        self.clients.append(Client(ws))

    def _send(self, client, message):
        try:
            client.ws.send_message(json.dumps(message), fail_silently=True)
        except OSError:
            client.ws.stalled = True
        if client.ws.stalled or client.ws.closed:
            self._drop(client)

    def _broadcast(self, message):
        text = json.dumps(message)
        for client in list(self.clients):
            try:
                client.ws.send_message(text, fail_silently=True)
            except OSError:
                client.ws.stalled = True
            if client.ws.stalled or client.ws.closed:
                self._drop(client)

    def _drop(self, client):
        self.remote.forget(client.name)
        if client in self.clients:
            self.clients.remove(client)
        try:
            client.ws.close()
        except OSError:
            pass

    def _poll_client(self, client):
        if not client.greeted:
            client.greeted = True
            hello = self.info()
            hello["t"] = "hello"
            hello["fields"] = hello.pop("telemetry_fields")
            self._send(client, hello)
        now = time.monotonic_ns()
        while client in self.clients:
            try:
                text = client.ws.receive(fail_silently=True)
            except OSError:
                self._drop(client)
                return
            if client.ws.closed:
                self._drop(client)
                return
            if text is None:
                break
            client.last_rx = now
            self._on_message(client, text)
        if now - client.last_rx > CLIENT_IDLE_S * NS_PER_S:
            print("Dropping idle client", client.name)
            self._drop(client)

    def _on_message(self, client, text):
        try:
            msg = json.loads(text)
            kind = msg.get("t")
        except (ValueError, AttributeError):
            self._send(client, {"t": "error", "text": "not JSON"})
            return
        if kind == "drive":
            error = self.remote.drive(msg.get("v"), msg.get("w"), client.name)
            if error:
                self._send(client, {"t": "error", "text": error})
        elif kind == "stop":
            self.stop(client.name)
        elif kind == "ping":
            self._send(client, {"t": "pong"})
        else:
            self._send(client, {"t": "error", "text": "unknown message type"})

    def stop(self, source):
        """Emergency stop: no ramp, latched until a v=0, w=0 request."""
        self.remote.stop(source)
        self.drive.stop()

    # --- settings ------------------------------------------------------

    def _wait_controller_params(self, version, seconds=0.15):
        """Read the link until the controller board answers with new settings."""
        end = time.monotonic_ns() + int(seconds * NS_PER_S)
        while self.controller.params_version == version and time.monotonic_ns() < end:
            self.controller.poll()

    def _set_params(self, body):
        errors = {}
        for name, value in body.get("wifi_board", {}).items():
            error = self.cfg.set(name, str(value))
            if error:
                errors[name] = error
        self.drive.apply_settings()
        controller_values = body.get("controller", {})
        if controller_values:
            version = self.controller.params_version
            self.controller.set_params(controller_values)
            self._wait_controller_params(version)
        return errors

    def _save_or_reset(self, request, reset):
        board = _body(request).get("board", "both")
        if board not in ("wifi_board", "controller", "both"):
            return _bad(request, "board must be wifi_board, controller or both")
        error = None
        if board in ("wifi_board", "both"):
            try:
                if reset:
                    self.cfg.reset()
                    self.drive.apply_settings()
                else:
                    self.cfg.save()
            except ValueError as e:
                error = str(e)
        if board in ("controller", "both"):
            version = self.controller.params_version
            if reset:
                self.controller.reset_params()
            else:
                self.controller.save_params()
            self._wait_controller_params(version)
        if error:
            return _bad(request, error)
        return JSONResponse(request, self.params())

    # --- routes ----------------------------------------------------------

    def _restart_soon(self):
        self.reboot_at = time.monotonic_ns() + NS_PER_S

    def _add_routes(self):
        server = self.server

        @server.route("/", GET)
        def page(request):
            return FileResponse(request, "index.html", WWW,
                                headers={"Cache-Control": "no-cache"})

        @server.route("/ws", GET)
        def websocket(request):
            ws = RobotWebsocket(request)
            self._add_client(ws)
            return ws

        @server.route("/api/info", GET)
        def get_info(request):
            return JSONResponse(request, self.info())

        @server.route("/api/telemetry", GET)
        def get_telemetry(request):
            sample = self.latest or [None] * len(TELEMETRY_FIELDS)
            return JSONResponse(request, dict(zip(TELEMETRY_FIELDS, sample)))

        @server.route("/api/drive", POST)
        def post_drive(request):
            body = _body(request)
            error = self.remote.drive(body.get("v"), body.get("w"), "http")
            if error:
                return _bad(request, error)
            return JSONResponse(request, {"ok": True})

        @server.route("/api/stop", POST)
        def post_stop(request):
            self.stop("http")
            return JSONResponse(request, {"ok": True})

        @server.route("/api/params", [GET, POST])
        def params(request):
            if request.method == POST:
                errors = self._set_params(_body(request))
                result = self.params()
                result["errors"] = errors
                return JSONResponse(request, result)
            return JSONResponse(request, self.params())

        @server.route("/api/params/save", POST)
        def params_save(request):
            return self._save_or_reset(request, reset=False)

        @server.route("/api/params/reset", POST)
        def params_reset(request):
            return self._save_or_reset(request, reset=True)

        @server.route("/api/wifi", GET)
        def wifi_info(request):
            return JSONResponse(request, self.wifi.info())

        @server.route("/api/wifi/scan", POST)
        def wifi_scan(request):
            if self.remote.active() or self.drive.moving():
                return _bad(request, "stop driving first")
            return JSONResponse(request, {"networks": self.wifi.scan()})

        @server.route("/api/wifi/test", POST)
        def wifi_test(request):
            if self.remote.active() or self.drive.moving():
                return _bad(request, "stop driving first")
            body = _body(request)
            if not body.get("ssid"):
                return _bad(request, "ssid missing")
            return JSONResponse(request, self.wifi.test(body["ssid"], body.get("password", "")))

        @server.route("/api/wifi/client", POST)
        def wifi_client(request):
            body = _body(request)
            error = self.wifi.save_client(body.get("ssid", ""), body.get("password", ""))
            if error:
                return _bad(request, error)
            self._restart_soon()
            return JSONResponse(request, {"ok": True, "restarting": True})

        @server.route("/api/wifi/ap", POST)
        def wifi_ap(request):
            body = _body(request)
            error = self.wifi.save_ap(body.get("ssid", ""), body.get("password", ""))
            if error:
                return _bad(request, error)
            self._restart_soon()
            return JSONResponse(request, {"ok": True, "restarting": True})

        @server.route("/api/wifi/name", POST)
        def wifi_name(request):
            error = self.wifi.save_name(_body(request).get("name", ""))
            if error:
                return _bad(request, error)
            self._restart_soon()
            return JSONResponse(request, {"ok": True, "restarting": True})

        @server.route("/api/wifi/reconnect", POST)
        def wifi_reconnect(request):
            if self.remote.active() or self.drive.moving():
                return _bad(request, "stop driving first")
            error = self.wifi.reconnect()
            if error:
                return _bad(request, error)
            return JSONResponse(request, self.wifi.info())

        @server.route("/api/wifi/forget", POST)
        def wifi_forget(request):
            self.wifi.forget()
            self._restart_soon()
            return JSONResponse(request, {"ok": True, "restarting": True})

