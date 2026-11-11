# Guide 6: differential drive kinematics

Code for part 6 of the
[RW-1 Build and Programming Guide](https://www.patreon.com/RoboticsWeekends/posts/6-rw-1-robot-175028720).
The theory is in the blog post
[Differential Drive Mobile Robot Kinematics](https://roboticsweekends.com/blogs/blog/differential-drive-mobile-robot-kinematics).

Builds on [`guide-5_closed-loop/`](../guide-5_closed-loop/): the robot is now
driven by its linear speed v (m/s) and angular speed w (rad/s). Inverse
kinematics turns them into wheel RPM targets for the part 5 speed controllers,
scaled down together when a wheel would go over the speed limit, and forward
kinematics turns the measured wheel speeds back into v and w. The requested
v and w are ramped within acceleration limits so the wheels don't slip.

Conventions: x points forward, positive w turns the robot left
(counter-clockwise), units are meters, seconds and radians.

## Files

| File | Purpose |
|---|---|
| `code.py` | Body speed demo, extended from part 5: follows a profile of (seconds, v, w) steps. `MODE` selects the wheel controller as in part 5; `PLOT` prints commanded and measured v and w (`"body"`) or the wheel RPM as in part 5 (`"wheels"`) for Thonny's Plotter |
| `check_kinematics.py` | Step 1, on blocks: checks wheel directions, wheel speeds and the speed limit scaling |
| `calibrate_wheel.py` | Step 2, on the floor: drives 2 m and prints a corrected `ROBOT_WHEEL_DIAMETER` |
| `calibrate_track.py` | Step 3, on the floor: spins 5 turns and prints a corrected `ROBOT_TRACK_WIDTH` |
| `rectangle.py` | Step 4, on the floor: drives a 1 x 0.5 m rectangle with stop-and-turn or rounded corners |
| `settings.toml` | Robot parameters, read on boot |
| `lib/kinematics.py` | New: inverse and forward kinematics, speed limit scaling |
| `lib/drive.py` | New: one control loop pass (measure, ramp, convert, compare and correct, drive) and `move()` by distance or angle. Holds `make_pid()` and `wheel_duty()` from part 5's `code.py`, so the scripts can share them |
| `lib/ticker.py` | New: the 20 ms timing from part 5's `code.py`, as a class that every script uses |
| `lib/pid.py`, `lib/encoder.py`, `lib/motor_controller.py`, `lib/robot.py`, `lib/pins.py` | From part 5, unchanged |
| `lib/config.py` | Loads `settings.toml`; adds the geometry, speed limit and acceleration settings |

The part 5 calibration scripts (`check_encoders.py`, `measure_ticks.py`,
`pwm_to_speed.py`) are not repeated here. They are in
[`guide-5_closed-loop/`](../guide-5_closed-loop/), and the values they found
are already in `settings.toml`.

## Usage

Copy the whole folder's contents to the CIRCUITPY drive with the robot on
blocks: `code.py` starts driving as soon as it's copied. Then:

1. `check_kinematics.py` (on blocks): every line should say `OK`.
2. `calibrate_wheel.py` (floor): copy the printed line into `settings.toml`.
3. `calibrate_track.py` (floor, after step 2): copy the printed line into `settings.toml`.
4. `rectangle.py` (floor): measure how far from the start mark the robot ends up.

## New settings

| Key | Default | Meaning |
|---|---|---|
| `ROBOT_WHEEL_DIAMETER` | `"0.080"` | Wheel diameter D, m |
| `ROBOT_TRACK_WIDTH` | `"0.195"` | Distance between the wheel centers L, m |
| `ROBOT_WHEEL_LIMIT_RPM` | `"170.0"` | Fastest wheel target the kinematics may ask for; below `ROBOT_MAX_RPM` so the PI controller keeps some PWM in reserve on the floor |
| `ROBOT_MAX_ACCEL` | `"0.5"` | Linear acceleration limit, m/s² |
| `ROBOT_MAX_ANG_ACCEL` | `"3.0"` | Angular acceleration limit, rad/s² |

Float values must be quoted in `settings.toml`.
