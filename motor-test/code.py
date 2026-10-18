"""
Minimal RW-1 differential-drive motor wiring check — two motors
(left + right), no encoders, no serial connection.

The program runs on power on (put the robot on blocks first):
  2 s idle -> move forward at 20% for 4 s   (straight)
  2 s idle -> turn right backward at 15% for 3 s  (spins clockwise)
  move forward at 20% for 4 s   (straight) -> turn right at 15% for 3 s

To run: copy this file to the CIRCUITPY drive. If a wheel spins the
wrong way, swap that motor's two leads or its FWD/BWD pins below.
"""
import time
import board
import pwmio

PWM_FREQ = 20000    # Hz
DUTY_MAX = 65535    # 16-bit duty scale (full on)

# H-bridge pins — defaults match code.py.
L_FWD = board.GP9
L_BWD = board.GP8
R_FWD = board.GP11
R_BWD = board.GP10

pwm_l_fwd = pwmio.PWMOut(L_FWD, frequency=PWM_FREQ, duty_cycle=0)
pwm_l_bwd = pwmio.PWMOut(L_BWD, frequency=PWM_FREQ, duty_cycle=0)
pwm_r_fwd = pwmio.PWMOut(R_FWD, frequency=PWM_FREQ, duty_cycle=0)
pwm_r_bwd = pwmio.PWMOut(R_BWD, frequency=PWM_FREQ, duty_cycle=0)


def set_wheel(pwm_fwd, pwm_bwd, duty):
    """Drive one wheel from a signed duty in -1.0 (reverse) .. 1.0 (forward)."""
    duty = int(max(-1.0, min(1.0, duty)) * DUTY_MAX)
    if duty >= 0:
        pwm_fwd.duty_cycle = duty
        pwm_bwd.duty_cycle = 0
    else:
        pwm_fwd.duty_cycle = 0
        pwm_bwd.duty_cycle = -duty


def drive(left, right):
    """Drive both wheels from signed duties."""
    set_wheel(pwm_l_fwd, pwm_l_bwd, left)
    set_wheel(pwm_r_fwd, pwm_r_bwd, right)


def idle():
    drive(0.0, 0.0)


# The robot moves forward, turns and moves back
idle()
time.sleep(2)
drive(0.20, 0.20)     # both wheels forward at 20% -> straight
time.sleep(4)
idle()
time.sleep(2)
drive(0.15, -0.15)    # left fwd / right back at 15% -> spins clockwise
time.sleep(3)
idle()
drive(0.20, 0.20)     # both wheels forward at 20% -> straight
time.sleep(4)
idle()
drive(0.15, -0.15)    # left fwd / right back at 15% -> spins clockwise
time.sleep(3)
idle()

