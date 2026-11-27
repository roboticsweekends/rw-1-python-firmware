# Guide 7: wireless control with ESP32-S3

Code for part 7 of the
[RW-1 Build and Programming Guide](https://www.patreon.com/cw/RoboticsWeekends/posts).
**The guide explains how it all works and how to set it up: start there.**

Builds on [`guide-6_kinematics/`](../guide-6_kinematics/): RW-1 gets a second
board, an ESP32-S3-Zero (the **Wi-Fi board**), wired to the Cytron Motion
2350 Pro (the **controller board**) over a serial link.

## What's new

- **Controller board**: keeps the wheel speed control from guide 5 and takes
  left/right wheel targets in RPM over the serial link.
- **Wi-Fi board**: runs the kinematics from guide 6 and sends the wheel
  targets. Adds the web page (drive, telemetry, settings, Wi-Fi set-up) and
  the JSON + WebSocket API (described at the top of `wifi/lib/web.py`).

## What you need

- Both boards, with the code from `controller/` and `wifi/` copied to their
  CIRCUITPY drives.
- `wifi/lib/adafruit_httpserver/` from the Adafruit library bundle.

| Folder | Goes to |
|---|---|
| `controller/` | the controller board's CIRCUITPY drive |
| `wifi/` | the Wi-Fi board's CIRCUITPY drive |

The robot's own network is `RW-1-XXXX` (password `rw1robot`), page at
`http://192.168.4.1`.
