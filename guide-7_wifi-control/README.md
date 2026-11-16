# Guide 7: wireless control with ESP32-S3

Code for part 7 of the
[RW-1 Build and Programming Guide](https://www.patreon.com/cw/RoboticsWeekends/posts).

RW-1 gets a second board, an ESP32-S3-Zero (the **Wi-Fi board**), wired to the Cytron Motion
2350 Pro (the **controller board**) over a serial link:

- the **controller board** keeps the wheel speed control from guide 5
  (encoders, feedforward + closed loop control, motors) and takes left/right wheel targets in RPM;
- the **Wi-Fi board** runs the kinematics from guide 6 (ramp, inverse and
  forward kinematics, wheel speed limit) and sends the wheel targets.

It also adds a web page (drive, live telemetry charts,
settings, Wi-Fi set-up) and a JSON + WebSocket API.

| Folder | Goes to |
|---|---|
| `controller/` | the controller board's CIRCUITPY drive |
| `wifi/` | the Wi-Fi board's CIRCUITPY drive |

## Wi-Fi

- **Access point, always on:** network `RW-1-XXXX`, password `rw1robot`,
  page at `http://192.168.4.1`.
- **Home network (optional):** set up from the web page or in
  `settings.toml`. The robot is then also at `http://rw-1.local` (not on
  every Android phone) and at the address the router gives it. The access
  point keeps running, on the home network's channel.
- **Forgetting Wi-Fi settings:** press BOOT in the first 3 s after
  power-up (right after, not before: holding BOOT while powering up starts
  the ESP32 bootloader instead). The console prints
  `BOOT pressed: saved Wi-Fi settings forgotten`.

## Web API

The web page and PC programs use the same API, described at the top of
`wifi/lib/web.py`:

- HTTP JSON: `/api/info`, `/api/telemetry`, `/api/drive`, `/api/stop`,
  `/api/params` (+ `/save`, `/reset`), `/api/wifi` (+ `/scan`, `/test`,
  `/client`, `/ap`, `/name`, `/reconnect`, `/forget`).
- WebSocket `/ws`: send `{"t": "drive", "v": m/s, "w": rad/s}` 10-20 times a
  second while driving, `{"t": "stop"}`, `{"t": "ping"}`; receive `hello`
  (with the telemetry column names), `tel` (5 samples every 100 ms), `state`
  (once a second).

Safety rules: no drive request for `CLIENT_TIMEOUT` = the robot stops with
its acceleration limits; STOP stops at once and is latched until the same
client sends v = 0 and w = 0 (another client can't end it, unless the one
that pressed STOP has disconnected; a STOP sent over plain HTTP can be
ended by any client); at most 2 WebSocket clients, the oldest is dropped for
a third; a client silent for 10 s is dropped.

## Web page

- **Drive:** drag the round pad (up = forward, left/right = turn), use
  the arrow keys or W A S D on a keyboard (space = STOP), or a gamepad's
  left stick (B = STOP; see [Gamepad](#gamepad) for the browser set-up).
  The Speed slider scales the robot's full speed. Requests go out 20 times
  a second while you drive; letting go sends one stop request.
- **Telemetry:** live charts of v, ω, the wheel speeds and the motor duty
  (50 samples a second). Record, then Download CSV, for analysis on the PC.
- **Settings:** the settings of both boards. Apply = use now, Save = keep
  after a restart, Reset = back to settings.toml. Grey values can only be
  changed in settings.toml.
- **Network:** where the robot can be reached, with a QR code for a phone;
  scan, test and save the home network; change the access point's name and
  password and the robot's name; forget everything. A banner asks to change
  the default access point password.

### Gamepad

Browsers only give a page access to gamepads when the page is "secure"
(`https://` or `localhost`). The robot's page is plain `http://`, so the
browser has to be told once to trust the robot's addresses. Until then the
Drive tab shows how to do it. Use every address you open the page with:
the name, the home network address and the access point's address.

**Chrome (PC and Android)**

1. Open `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.
2. In the text box, enter the robot's addresses with `http://`, separated
   by commas, for example
   `http://rw-1.local,http://192.168.1.50,http://192.168.4.1`.
3. Set the flag to **Enabled** and press **Relaunch**.

**Firefox (PC)**

1. Open `about:config` and accept the warning.
2. Search for `dom.securecontext.allowlist`. If it doesn't exist, choose
   **String** and press **+**.
3. Enter the robot's host names without `http://`, separated by commas,
   for example `rw-1.local,192.168.1.50,192.168.4.1`.
4. Reload the robot's page.

Firefox for Android only opens `about:config` in its Beta and Nightly
versions; on a phone, use Chrome.

Then open the robot's page, connect the gamepad and press any button: the
Drive tab shows the gamepad's name. The left stick drives (15 % dead zone),
B stops. If the robot's address changes (a new home network), add the new
one.
