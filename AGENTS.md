# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this repository is

CircuitPython firmware for **RW-1**, a small differential-drive robot by
Robotics Weekends. The code is written step by step in the
**["RW-1 Build and Programming Guide"](https://www.patreon.com/cw/RoboticsWeekends/posts)**: each guide in the series adds a piece of
functionality, and this repository keeps the code exactly as it stands at the
end of each guide.

Target hardware:

- **Board:** Cytron Motion 2350 Pro (RP2350), running CircuitPython
- **Motors:** two DC gear motors on the board's M1 (left) and M2 (right) H-bridge channels
- **Encoders:** two quadrature encoders read with `rotaryio`
- **From guide 7:** a second board, an ESP32-S3-Zero (the "Wi-Fi board"), also
  running CircuitPython, wired to the Motion 2350 Pro (the "controller board")
  over a 921600-baud serial link

## Repository layout

```
guide-N_<topic>/   Code developed in guide N, frozen at the end of that guide
recent/            The latest firmware: a copy of the newest guide-N_* folder
AGENTS.md          This file
README.md          Project overview
```

Current folders:

| Folder | Guide | Content |
|---|---|---|
| `guide-3_motor-test/` | 3 | Single-file open-loop motor wiring check |
| `guide-5_closed-loop/` | 5 | Encoders, calibration scripts, feedforward + PI wheel speed control |
| `guide-6_kinematics/` | 6 | Differential drive kinematics: body speed (v, w) control, wheel and track calibration, rectangle test |
| `guide-7_wifi-control/` | 7 | Wi-Fi board: serial link, web server, web page, JSON/WebSocket API |
| `recent/` | latest | Same code as `guide-7_wifi-control/` |

Guides that only cover mechanics or electronics have no folder.

Each folder is a complete, self-contained **CIRCUITPY drive image**: its
contents are copied as-is to the root of the board's CIRCUITPY drive.
`code.py` runs on boot, `lib/` holds the modules it imports, and
`settings.toml` holds the robot's tunable parameters.

From guide 7 on, a guide folder holds one image per board:

```
guide-7_wifi-control/
  controller/   CIRCUITPY image for the controller board (Motion 2350 Pro)
  wifi/         CIRCUITPY image for the Wi-Fi board (ESP32-S3-Zero)
  README.md
```

`lib/link.py` and `lib/store.py` are the same file in `controller/` and
`wifi/`: change both together.
`wifi/lib/adafruit_httpserver/` is not in the repo (readers copy it from the
Adafruit library bundle).

## Rules for changes

1. **Guide folders are snapshots.** Do not refactor or extend an existing
   `guide-N_*` folder: readers follow the guide text against that code. Only
   fix real bugs or typos there, and only when asked.
2. **New guide = new folder.** Code for a new guide goes into a new
   `guide-N_<short-kebab-topic>/` folder, usually started as a copy of
   `recent/`.
3. **Keep `recent/` in sync.** After a new guide folder is finished, make
   `recent/` match it (`diff -r guide-N_<topic> recent` should show only the
   folders' `README.md` files). A bug fix in the latest guide folder is
   applied to `recent/` too.
4. **Each folder stands alone.** No imports across folders, no shared
   top-level `lib/`. Duplicated modules between folders are intentional.
5. Keep each folder's `README.md` up to date when files are added or their
   purpose changes, and add the new guide to the tables in `README.md` and here.

## CircuitPython conventions

- The code runs on a microcontroller under CircuitPython, not CPython. Use only
  modules available there (`board`, `pwmio`, `rotaryio`, `time`, `os`, ...). No
  `typing`, `dataclasses`, `asyncio` unless the guide introduces it, no pip packages.
- Keep the control loop allocation-free where possible (see `lib/pid.py`) and
  avoid heavy work inside it.
- Format strings with `"...".format(...)`, as the existing code does.
- `settings.toml` only supports strings and integers: **float values must be
  quoted** (`ROBOT_MAX_RPM="200.0"`). New parameters are added to both
  `settings.toml` and the `_FIELDS` table in `lib/config.py`, with a default.
- All pin assignments live in `lib/pins.py`; hardware objects are built in
  `lib/robot.py` (`make_motors()`, `make_encoders()`). Scripts should not
  create `PWMOut` or `IncrementalEncoder` objects directly.
- Encoder A/B pins must be consecutive GPIOs (`rotaryio` uses the RP2350 PIO).
- Motor duty is a signed integer in `-65535 .. 65535` (`robot.DUTY_MAX`);
  `robot.duty(fraction)` converts from `-1.0 .. 1.0`.
- Output meant for Thonny's Plotter uses `label: value` pairs on one line.
- New source files start with the SPDX header used in the existing files:

  ```python
  # SPDX-FileCopyrightText: 2026 Robotics Weekends
  # SPDX-License-Identifier: MIT
  ```

- Code is read by guide readers, many of them beginners: prefer plain, short,
  well-commented code over clever abstractions.
- Wi-Fi board: no `asyncio`, a plain loop that never sleeps (`ticker.due()`);
  anything slow (scans, connecting) is refused while the robot is
  driven. The web page `wifi/www/index.html` is one self-contained file with
  no internet resources (it must work on the robot's own access point).
- Safety rules that must survive changes: the client timeout (the robot stops
  when drive requests stop), the controller's link timeout, the STOP latch
  (only the client that pressed STOP ends it).

## Testing

There is no automated test suite and the board code cannot run on a desktop
Python (it needs `board`, `pwmio`, `rotaryio`). A syntax check is the most that
can be done locally:

```bash
python3 -m py_compile recent/*.py recent/lib/*.py                       # guides 3-6
python3 -m py_compile recent/*/*.py recent/controller/lib/*.py recent/wifi/lib/*.py   # guide 7 on
```

Behaviour is verified on the robot itself (wheels lifted off the ground). Say
so when a change has not been tested on hardware.
