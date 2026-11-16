# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Record the robot's telemetry to a CSV file, while you drive it from the web
page (or while another script drives it).

    python record.py                       # until Ctrl+C, robot at rw-1.local
    python record.py --seconds 20 --host 192.168.4.1 --out run1.csv

One row per sample (50 a second), the same columns as the web page's CSV:
t_s (seconds from the start), then the robot's telemetry fields: ms,
v_cmd, w_cmd, v, w, target_l, target_r, rpm_l, rpm_r, duty_l, duty_r,
pos_l, pos_r.
"""
import argparse
import csv
import time

from rw1_client import Robot


def main():
    parser = argparse.ArgumentParser(description="Record the robot's telemetry to CSV.")
    parser.add_argument("--host", default="rw-1.local")
    parser.add_argument("--seconds", type=float, default=0, help="0 = until Ctrl+C")
    parser.add_argument("--out", default=time.strftime("rw1-%Y%m%d-%H%M%S.csv"))
    args = parser.parse_args()

    robot = Robot(args.host).connect()
    rows = []
    clock = {"t": 0.0, "last_ms": None}

    def on_samples(samples):
        for s in samples:
            # The controller's ms counter wraps at 65536: keep our own time
            if clock["last_ms"] is not None:
                clock["t"] += ((s["ms"] - clock["last_ms"]) % 65536) / 1000
            clock["last_ms"] = s["ms"]
            rows.append([round(clock["t"], 3)] + [s[f] for f in robot.fields])

    robot.on_samples = on_samples
    print("Recording to {} (Ctrl+C to stop)".format(args.out))
    start = time.monotonic()
    try:
        while not args.seconds or time.monotonic() - start < args.seconds:
            robot.keep_alive()
            time.sleep(0.5)
            print("\r{} samples".format(len(rows)), end="", flush=True)
    except KeyboardInterrupt:
        pass
    robot.close()

    with open(args.out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t_s"] + robot.fields)
        writer.writerows(rows)
    print("\nSaved {} samples to {}".format(len(rows), args.out))


if __name__ == "__main__":
    main()
