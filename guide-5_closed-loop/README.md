# Guide 5: Closed-loop wheel speed control

Code from guide 5 of the [RW-1 Build and Programming Guide](https://www.patreon.com/cw/RoboticsWeekends/posts).

Adds the wheel encoders, three calibration scripts and a wheel speed
controller (feedforward + PI, 50 Hz) that makes each wheel hold a target RPM.

## Files

| File | Purpose |
|---|---|
| `code.py` | Speed control demo: follows a profile of left/right target RPM steps and prints target and measured speed for Thonny's Plotter. `MODE` selects `"open"`, `"p"` or `"pi"` |
| `check_encoders.py` | Step 1: checks that both encoders count, and count up when the wheel turns forward |
| `measure_ticks.py` | Step 2: measures encoder counts per wheel revolution (`ROBOT_TICKS_PER_REV`) |
| `pwm_to_speed.py` | Step 3: measures RPM against PWM and suggests `ROBOT_MAX_RPM`, `ROBOT_FF_LEFT`, `ROBOT_FF_RIGHT` |
| `settings.toml` | Robot parameters, read on boot |
| `lib/pins.py` | Pin map for motors and encoders |
| `lib/config.py` | Loads `settings.toml` into a `RobotConfig` object, with defaults |
| `lib/robot.py` | Builds the motor and encoder objects from the pin map and config |
| `lib/motor_controller.py` | Signed-duty PWM driver for the two H-bridge channels |
| `lib/encoder.py` | Reads both quadrature encoders and computes filtered wheel RPM |
| `lib/pid.py` | PID controller with feedforward and integral anti-windup |

## Usage

Copy the whole folder's contents to the CIRCUITPY drive and keep the robot on
blocks. Only `code.py` runs on boot; run the calibration scripts in order from
Thonny (or temporarily rename one to `code.py`):

1. `check_encoders.py`: fix encoder wiring or direction if it reports a problem.
2. `measure_ticks.py`: put the printed `ROBOT_TICKS_PER_REV` into `settings.toml`.
3. `pwm_to_speed.py`: copy the printed lines into `settings.toml`.

Then run `code.py` and watch the speeds in Thonny's Plotter.

## settings.toml

CircuitPython's `settings.toml` only supports strings and integers, so
**float values must be quoted**, e.g. `ROBOT_MAX_RPM="200.0"`. Missing or
invalid values fall back to the defaults in `lib/config.py`.
