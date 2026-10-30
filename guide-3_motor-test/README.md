# Guide 3: Motor test

Code from guide 3 of the [RW-1 Build and Programming Guide](https://www.patreon.com/cw/RoboticsWeekends/posts).

A single `code.py` that checks the motor wiring. No encoders and no extra
libraries are needed.

## Files

| File | Purpose |
|---|---|
| `code.py` | Drives both wheels in a fixed open-loop sequence on power on |

## Usage

1. Put the robot on blocks so the wheels spin freely.
2. Copy `code.py` to the CIRCUITPY drive.
3. The robot repeats twice: wait, both wheels forward at 20% for 4 s, then
   spin clockwise (left forward, right backward) at 15% for 3 s.

If a wheel turns the wrong way, swap that motor's two leads, or swap its
FWD/BWD pins at the top of `code.py`.
