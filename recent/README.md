# Recent: latest RW-1 firmware

This folder always holds the latest RW-1 firmware. It is currently the same
code as [`guide-8_pc-control/`](../guide-8_pc-control/) (PC control and code
updates over Wi-Fi), part 8 of the
[RW-1 Build and Programming Guide](https://www.patreon.com/cw/RoboticsWeekends/posts),
and will be updated as new guides are published.

Builds on [`guide-7_wifi-control/`](../guide-7_wifi-control/), the same two
boards (controller board and Wi-Fi board).

## What's new

- **`pc/`**: Python scripts for your PC. `rw1_client.py` is the RW-1 API
  module to import in your own programs; `find_robot.py`, `record.py` and
  `drive_square.py` are examples.
- **Code updates over Wi-Fi**: the web page's Update tab sends new code to
  either board (`boot.py`, `lib/updates.py` and the update modules).

## What you need

- Both boards from guide 7, with the code from `controller/` and `wifi/`
  copied to their CIRCUITPY drives (one more USB copy, including `boot.py`).
- `wifi/lib/adafruit_httpserver/` from the Adafruit library bundle.
- For `pc/`: Python 3.8+ on your PC, nothing else to install.

| Folder | Goes to |
|---|---|
| `controller/` | the controller board's CIRCUITPY drive |
| `wifi/` | the Wi-Fi board's CIRCUITPY drive |
| `pc/` | your PC |

## Your own program

```python
from rw1_client import find_robots, Robot

host, info = find_robots()[0]
with Robot(host).connect() as robot:
    robot.drive_distance(0.5)       # 0.5 m forward, by the encoders
    robot.turn_angle(90)            # 90 degrees left
```
