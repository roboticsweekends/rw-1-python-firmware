# rw-1-python-firmware

CircuitPython firmware and Python scripts for **RW-1**, a differential-drive
robot by Robotics Weekends.

This repository is the companion code for the Robotics Weekends
**["RW-1 Build and Programming Guide"](https://www.patreon.com/cw/RoboticsWeekends/posts)**. Each guide in the series builds on the
previous one, and the code here is kept exactly as it stands at the end of
each guide, so you can follow along step by step or jump straight to the
latest firmware.

## Hardware

- Cytron Motion 2350 Pro (RP2350) controller running CircuitPython
- Two DC gear motors on the board's M1 (left) and M2 (right) channels
- Two quadrature wheel encoders

## Repository layout

| Folder | Guide | What it contains |Post|
|---|---|---|---|
| [`guide-3_motor-test/`](guide-3_motor-test/) | 3 | Motor wiring check: drives both wheels open loop, no encoders | [Link](https://www.patreon.com/RoboticsWeekends/posts/3-rw-1-robot-172695270) |
| [`guide-5_closed-loop/`](guide-5_closed-loop/) | 5 | Encoder check, calibration scripts and closed-loop (feedforward + PI) wheel speed control | [Link](https://www.patreon.com/RoboticsWeekends/posts) |
| [`recent/`](recent/) | latest | The final state of the firmware, currently the same as `guide-5_closed-loop/` |

- `guide-N_<topic>/` folders hold the code developed in guide N. They are
  snapshots: they don't change when later guides add new features.
- `recent/` always holds the latest firmware. Use it if you just want the
  most up-to-date code for your robot.

Guides without a folder cover mechanics and electronics only.

## Installing on the robot

1. Install CircuitPython on the Cytron Motion 2350 Pro and connect it over USB.
   It shows up as a drive named **CIRCUITPY**.
2. Pick a folder (`recent/` or the `guide-N_*` folder you are working on) and
   copy **its contents** to the root of the CIRCUITPY drive, replacing what is
   there.
3. The board restarts and runs `code.py`. Open the serial console (for example
   in Thonny) to see its output.

Put the robot on blocks with the wheels off the ground before the first run.

Robot parameters (wheel size, encoder counts, controller gains, ...) are in
`settings.toml` on the CIRCUITPY drive; see the folder's README for details.

## License

See [LICENSE](LICENSE).
