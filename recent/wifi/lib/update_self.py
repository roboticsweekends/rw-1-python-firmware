# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Update mode of the Wi-Fi board: receive its own new code files from the
web page and put them in place.
"""
import time

import microcontroller
import socketpool
import wifi
from adafruit_httpserver import BAD_REQUEST_400, GET, POST, JSONResponse, Response, Server

import updates
from wifi_setup import WifiSetup

IDLE_TIMEOUT_S = 300

PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>RW-1 update</title></head>
<body style="font-family:system-ui;padding:16px"><h1>Update mode</h1>
<p>The robot is waiting for new files from the page that started the update.
If that page was closed, wait {} minutes: the robot then restarts with its old code.</p></body></html>
""".format(IDLE_TIMEOUT_S // 60)


def run():
    """Never returns: the board resets at the end."""
    updates.clean_up()
    print("Update mode: waiting for files from the web page")
    net = WifiSetup()
    net.start()
    pool = socketpool.SocketPool(wifi.radio)
    server = Server(pool, "/www", debug=False)
    server.socket_timeout = 2
    received = []
    state = {"last": time.monotonic(), "reset_at": None, "keep": False}

    def bad(request, text):
        return JSONResponse(request, {"ok": False, "error": text}, status=BAD_REQUEST_400)

    @server.route("/", GET)
    def page(request):
        return Response(request, PAGE, content_type="text/html")

    @server.route("/api/update/status", GET)
    def status(request):
        state["last"] = time.monotonic()
        return JSONResponse(request, {"mode": "update", "files": received})

    @server.route("/api/update/file", POST)
    def upload(request):
        state["last"] = time.monotonic()
        name = request.query_params.get("name", "")
        problem = updates.check_name(name)
        if problem:
            return bad(request, "{}: {}".format(name, problem))
        data = request.body
        try:
            size = int(request.query_params.get("size", "-1"))
        except ValueError:
            size = -1
        if size != len(data):
            return bad(request, "{}: got {} of {} bytes, send it again".format(name, len(data), size))
        if size > updates.MAX_FILE or size + 4096 > updates.free_space():
            return bad(request, "{}: too big".format(name))
        with open(name + ".new", "wb") as f:
            f.write(data)
        if name not in received:
            received.append(name)
        print("Received", name, size, "bytes")
        return JSONResponse(request, {"ok": True, "name": name, "size": size})

    @server.route("/api/update/commit", POST)
    def commit(request):
        updates.swap_in(received)
        print("Update done:", ", ".join(received))
        state["keep"] = True
        state["reset_at"] = time.monotonic() + 1
        return JSONResponse(request, {"ok": True, "files": received, "restarting": True})

    @server.route("/api/update/abort", POST)
    def abort(request):
        state["reset_at"] = time.monotonic() + 1
        return JSONResponse(request, {"ok": True, "restarting": True})

    server.start("0.0.0.0", 80)
    print("Update mode ready at http://{}".format(net.ip_client() or "192.168.4.1"))
    while True:
        try:
            server.poll()
        except OSError as error:
            print("HTTP error:", error)
        now = time.monotonic()
        if state["reset_at"] is not None and now >= state["reset_at"]:
            break
        if now - state["last"] > IDLE_TIMEOUT_S:
            print("No files for {} s".format(IDLE_TIMEOUT_S))
            break
    if not state["keep"]:
        updates.clean_up()
        print("Update cancelled, restarting with the old code")
    time.sleep(0.2)
    microcontroller.reset()
