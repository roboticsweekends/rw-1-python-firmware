# Recent: latest RW-1 firmware

This folder always holds the latest RW-1 firmware. It is currently the same
code as [`guide-8_pc-control/`](../guide-8_pc-control/) (PC control and code
updates over Wi-Fi), part 8 of the
[RW-1 Build and Programming Guide](https://www.patreon.com/cw/RoboticsWeekends/posts),
and will be updated as new guides are published.

Builds on [`guide-7_wifi-control/`](../guide-7_wifi-control/), the same two
boards: an ESP32-S3-Zero (the **Wi-Fi board**), wired to the Cytron Motion
2350 Pro (the **controller board**) over a serial link. The controller board
runs the wheel speed control, the Wi-Fi board the kinematics, the web page and
the JSON and WebSocket API.

This part adds:

- **Python scripts for the PC** (`pc/`): a client for your own programs,
  finding the robot on the network, recording telemetry to CSV, and driving a
  square on its own using the wheel encoders;
- **code updates over Wi-Fi**: the web page's new Update tab sends new code
  to either board, so after one more USB copy the cable stays in the drawer.

## What's new since guide 7

- New on both boards: `boot.py` and `lib/updates.py` (the same files on both).
- Controller board: new `lib/updater.py`; `code.py` restarts into it when
  asked (`cmd=update`) and says in its hello whether `boot.py` is there.
- Wi-Fi board: new `lib/update_controller.py` and `lib/update_self.py`;
  `code.py` starts the update mode when asked and sends files to the
  controller board; `lib/web.py` has the `/api/update/...` routes;
  `www/index.html` has the Update tab; `lib/controller.py` reads the
  controller board's `boot=` flag.
- New folder `pc/`.

| Folder | Goes to |
|---|---|
| `controller/` | the controller board's CIRCUITPY drive |
| `wifi/` | the Wi-Fi board's CIRCUITPY drive |
| `pc/` | your PC (plain Python 3.8+) |

## Wiring

| Controller board (Motion 2350 Pro) | Wi-Fi board (ESP32-S3-Zero) |
|---|---|
| Servo port 4 signal, GP4 (UART1 TX) | GPIO2 (RX) |
| Servo port 5 signal, GP5 (UART1 RX) | GPIO1 (TX) |
| Servo port GND | GND |
| Servo port +5V, through a 1N5817 Schottky diode (stripe toward the Wi-Fi board) | 5V |

The diode keeps the robot's 5 V out of the PC's USB port when the Wi-Fi
board is plugged in: the ESP32-S3-Zero's 5V pin is wired straight to its
USB connector. A Schottky diode drops only about 0.3-0.45 V, so the board
still gets about 4.6 V; a plain silicon diode such as the 1N4007 drops
0.7-1 V and leaves less margin for Wi-Fi current peaks.

For a bench test with the Wi-Fi board on USB, the 5V wire can be left out:
TX, RX and GND are enough.

## Serial link (`lib/link.py`, the same file on both boards)

921600 baud. Every message is one frame:
`0xA5 | type | length | payload | checksum`, where the checksum is the low
byte of the sum of type, length and payload.

| Frame | Direction | Payload | Frame size |
|---|---|---|---|
| `W` targets | Wi-Fi → controller | left, right target, int16 in 0.01 RPM | 8 bytes |
| `T` telemetry | controller → Wi-Fi | ms (uint16), encoder counts (2 × int32), measured RPM, target RPM (int16, 0.01 RPM), duty (int16, 0.01 %) | 26 bytes |
| `X` stop | Wi-Fi → controller | none | 4 bytes |
| `C` text | both | `cmd=... key=value ...`; long messages are split, all parts but the last carry `more=1` | up to 259 bytes |
| `F` file | both, code updates only | Wi-Fi → controller: part number (uint16), Adler-32 of the part (uint32), up to 240 bytes of a file; controller → Wi-Fi: the part number as an ack | up to 250 bytes |

The Wi-Fi board sends `W` every `DRIVE_PERIOD_MS` (20 ms); the controller
board sends `T` every `TELEMETRY_EVERY` passes of its loop. Text commands to
the controller board: `cmd=hello`, `cmd=get`, `cmd=set name=value ...`,
`cmd=save`, `cmd=reset`. It answers `cmd=hello`, `cmd=params`
(all settings, `saved=` and `live=` lists, `errors=` after a bad `set`),
and sends `cmd=event name=timeout` when it stopped the motors
because the targets stopped coming. `cmd=update` restarts it into its
updater (see [Code updates](#code-updates)); the updater's commands are
described at the top of `controller/lib/updater.py`.

## Files

### `controller/`: Cytron Motion 2350 Pro

| File | Purpose |
|---|---|
| `code.py` | Wheel speed server: reads frames, stops the motors if no targets arrive for `LINK_TIMEOUT`, runs the wheel speed control, sends telemetry |
| `boot.py` | New: makes the drive writable for a code update; copied over USB once, never replaced over Wi-Fi |
| `settings.toml` | Wheel speed control settings (from guides 5 and 6) and the link settings |
| `lib/wheels.py` | both wheels' speed controllers; `make_pid()` and `wheel_duty()` from guide 6's `drive.py` |
| `lib/link.py` | serial link frames |
| `lib/store.py` | settings saved from the web page, kept in NVM |
| `lib/updates.py` | New: code update helpers shared by both boards (update flag, file checks, safe file swap) |
| `lib/updater.py` | New: receives new code files from the Wi-Fi board |
| `lib/config.py` | Loads `settings.toml`, then the saved values; live settings can be changed through the link |
| `lib/pins.py` | Guide 6 pins + `LINK_TX`/`LINK_RX` |
| `lib/pid.py`, `lib/encoder.py`, `lib/motor_controller.py`, `lib/robot.py`, `lib/ticker.py` | From guide 6, unchanged |

Guide 6's `kinematics.py`, `drive.py` and its calibration scripts are not
here: the kinematics moved to the Wi-Fi board.

### `wifi/`: ESP32-S3-Zero

| File | Purpose |
|---|---|
| `code.py` | Wi-Fi, web server and drive loop (see below) |
| `boot.py` | New: the same file as on the controller board |
| `check_link.py` | Run once after wiring, robot on blocks: checks the link, the telemetry rate, each wheel's direction and the link timeout |
| `settings.toml` | Geometry, speed limit and acceleration settings (from guide 6), the link settings, Wi-Fi settings |
| `www/index.html` | The web page (one file, no internet needed): Drive, Telemetry, Settings, Network and Update tabs |
| `lib/web.py` | web server, JSON API and WebSocket (`adafruit_httpserver`) |
| `lib/wifi_setup.py` | access point, home network, mDNS name |
| `lib/remote.py` | drive requests from the web page or PC, the client timeout and the latched STOP |
| `lib/adafruit_httpserver/` | From the Adafruit CircuitPython library bundle for CircuitPython 10.x |
| `lib/drive.py` | Guide 6's `drive.py` without the wheel control: measure (from telemetry), ramp, convert, send the targets; `limits()` gives the fastest v and w |
| `lib/controller.py` | the controller board as seen through the link (newest telemetry, its settings) |
| `lib/kinematics.py` | From guide 6, unchanged |
| `lib/ticker.py` | From guide 6, plus `due()`: the same timing without sleeping |
| `lib/update_controller.py` | New: sends new code files to the controller board |
| `lib/update_self.py` | New: update mode of this board: receives its own new files from the web page |
| `lib/link.py`, `lib/store.py`, `lib/updates.py` | The same files as on the controller board |
| `lib/config.py` | Loads `settings.toml`, then the saved values |
| `lib/pins.py` | Link pins (GPIO1 TX, GPIO2 RX, next to the power pins; change them here for another ESP32-S3 board), BOOT button |

### `pc/`: scripts for the PC

Plain Python 3.8 or newer on Windows, macOS or Linux, standard library only
(nothing to install with pip). They use the same API as the web page.

| File | Purpose |
|---|---|
| `rw1_client.py` | `Robot` class: settings and telemetry over HTTP, driving and live telemetry over the WebSocket. Import it in your own scripts |
| `find_robot.py` | Finds robots by name, on the access point, and by scanning your PC's network |
| `record.py` | Records the telemetry to a CSV file (the same columns as the web page's CSV) while you drive |
| `drive_square.py` | Drives a square, using the wheel encoders to end each side and each turn |

## Settings

Controller board (`controller/settings.toml`), new in guide 7:

| Key | Default | Meaning |
|---|---|---|
| `CONTROL_PERIOD_MS` | `20` | Control loop period, ms |
| `TELEMETRY_EVERY` | `1` | Send telemetry every N passes |
| `LINK_BAUD` | `921600` | Link speed; the same on both boards |
| `LINK_TIMEOUT` | `"0.3"` | Stop the motors if no targets arrive for this long, s |

Wi-Fi board (`wifi/settings.toml`): guide 6's `ROBOT_WHEEL_DIAMETER`,
`ROBOT_TRACK_WIDTH`, `ROBOT_WHEEL_LIMIT_RPM`, `ROBOT_MAX_ACCEL`,
`ROBOT_MAX_ANG_ACCEL`, plus:

| Key | Default | Meaning |
|---|---|---|
| `DRIVE_PERIOD_MS` | `20` | How often the wheel targets are sent, ms |
| `LINK_BAUD` | `921600` | Link speed; the same on both boards |
| `CONTROLLER_TIMEOUT` | `"0.5"` | No telemetry for this long = link lost, s |
| `CLIENT_TIMEOUT` | `"0.5"` | No drive request from the web page or PC for this long = stop, s |
| `ROBOT_NAME` | `"rw-1"` | The robot's name; on the home network it's `http://rw-1.local` |
| `AP_SSID` | `""` | Access point name; empty = `RW-1-` + the last 4 hex digits of the MAC address |
| `AP_PASSWORD` | `"rw1robot"` | Access point password, 8 to 63 characters |
| `WIFI_SSID`, `WIFI_PASSWORD` | `""` | Home network; usually set up from the web page instead |

Don't use the `CIRCUITPY_WIFI_SSID` keys: they start CircuitPython's own web
workflow, which takes port 80.

Float values must be quoted in `settings.toml`. Values changed and saved
from the web page are kept in each board's NVM and win over
`settings.toml` until "Reset"; only values that differ from
`settings.toml` are saved.

## Wi-Fi

- **Access point, always on:** network `RW-1-XXXX`, password `rw1robot`,
  page at `http://192.168.4.1`.
- **Home network (optional):** set up from the web page or in
  `settings.toml`. The robot is then also at `http://rw-1.local` (not on
  every Android phone) and at the address the router gives it. The access
  point keeps running, on the home network's channel.
- **Home network gone:** after 30 s the robot stops looking for it (looking
  disturbs the access point) and tries again every 5 minutes while it isn't
  driven, or when asked through `/api/wifi/reconnect`.
- **Forgetting Wi-Fi settings:** press BOOT in the first 3 s after
  power-up (right after, not before: holding BOOT while powering up starts
  the ESP32 bootloader instead). The console prints
  `BOOT pressed: saved Wi-Fi settings forgotten`.

## Web API

The web page and PC programs use the same API, described at the top of
`wifi/lib/web.py`:

- HTTP JSON: `/api/info`, `/api/telemetry`, `/api/drive`, `/api/stop`,
  `/api/params` (+ `/save`, `/reset`), `/api/wifi` (+ `/scan`, `/test`,
  `/client`, `/ap`, `/name`, `/reconnect`, `/forget`), `/api/update` (+
  `/status`, `/file`, `/clear`, `/controller`, `/wifi_board`).
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

## Usage

1. Put the robot on blocks. Copy `controller/` to the controller board's
   CIRCUITPY drive and `wifi/` to the Wi-Fi board's, plus
   `lib/adafruit_httpserver/` from the library bundle. Keep your own
   `settings.toml` values and `lib/pins.py` (from guide 6 on the controller
   board, from guide 7 on the Wi-Fi board). Both folders include `boot.py`:
   after this copy, later code changes can go over Wi-Fi (see
   [Code updates](#code-updates)).
2. On the Wi-Fi board, run `check_link.py` from the REPL: every line should
   say `OK`.
3. Restart the Wi-Fi board, join its network `RW-1-XXXX` from a phone and
   open `http://192.168.4.1`.

## PC scripts

Run them from the `pc/` folder, with the PC on the same network as the
robot (its access point, or your home network). `--host` takes the robot's
name or address; the default is `rw-1.local`.

```
python find_robot.py
python record.py --seconds 20 --out run1.csv
python drive_square.py --side 0.5            # --right to turn right
```

`drive_square.py` needs about side + 0.3 m of free floor ahead and to the
left. Ctrl+C or STOP on the web page stops it.

Using the client in your own script:

```python
from rw1_client import Robot

with Robot("rw-1.local").connect() as robot:
    robot.drive_for(0.2, 0.0, 2.0)      # 0.2 m/s for 2 s, then stop
    print(robot.sample["v"], robot.sample["rpm_l"])
```

A script must keep sending drive requests (`drive_for()` does it 20 times a
second): the robot stops by itself 0.5 s after the last one. Leaving the
`with` block stops the robot. A STOP pressed on the web page holds the robot
until that page lets go; the script's requests are refused meanwhile and it
sees why in `robot.errors`.

## Code updates

The Update tab of the web page sends new code to either board over Wi-Fi,
for example after you changed a file in this folder on the PC.

1. Choose the board's folder (`controller/` or `wifi/`) or single files.
   Files the robot doesn't use are left out; `settings.toml` and
   `lib/pins.py` are listed but not ticked, so your calibration and wiring
   stay unless you tick them.
2. Press **Update**. The robot must stand still: the motors are off during
   the update.
   - Controller board: the files go to the Wi-Fi board first, then over the
     serial link to the controller board, which restarts into its updater.
     A few seconds; the page waits.
   - Wi-Fi board: it restarts into update mode (same networks, same
     addresses), the page sends the files, the board restarts with them and
     the page reloads.
3. Every file is written as `<name>.new` and checked (size and Adler-32
   checksum). Only when all files are good, the old files are replaced. If
   anything goes wrong (power lost, Wi-Fi lost, a damaged file), the board
   restarts with its old code.

How it works: CircuitPython can only write to its own drive after `boot.py`
made the drive writable, and `boot.py` only runs after a reset. So the
board sets a flag in its NVM and resets; `boot.py` sees the flag, makes the
drive writable for this one start (the PC sees CIRCUITPY read-only
meanwhile) and `code.py` runs the updater instead of the normal program.
The next restart is normal again. Details: `lib/updates.py`.

`boot.py` itself is never replaced over Wi-Fi: it is the way back. If an
update leaves a board in a bad state, fix the files over USB as usual, or
double-press the board's reset button for safe mode (skips `boot.py` and
`code.py`). CircuitPython itself (the `.uf2` firmware) is still updated
over USB.

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
- **Update:** new code for either board over Wi-Fi; see
  [Code updates](#code-updates).

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

## Test status

Tested on the robot: the serial link, Wi-Fi (access point and home network
together), the web page with all its tabs, settings, safety stops, the
gamepad (Firefox on a PC), the PC scripts, and code updates over Wi-Fi for
both boards (7-10 s per update). Tested only in a desktop simulation
(simulated boards, motors, serial link and Wi-Fi): an update interrupted by a
power loss, by a closed page or by a noisy serial link, which all end with
the old code still running.

Known issue: on one Samsung Galaxy S25 with Chrome the page doesn't open
(other phones, including a Galaxy S20, work).
