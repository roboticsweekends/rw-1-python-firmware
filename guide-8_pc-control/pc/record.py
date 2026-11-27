# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Record the robot's telemetry to a CSV file.

    python record.py --seconds 20 --host 192.168.4.1 --out run1.csv
"""
import argparse
import time

from rw1_client import Robot, RobotError, Recorder


def main():
    parser = argparse.ArgumentParser(description="Record the robot's telemetry to CSV.")
    parser.add_argument("--host", default="rw-1.local")
    parser.add_argument("--seconds", type=float, default=0, help="0 = until Ctrl+C")
    parser.add_argument("--out", default=time.strftime("rw1-%Y%m%d-%H%M%S.csv"))
    args = parser.parse_args()

    robot = Robot(args.host).connect()
    recorder = Recorder(robot)
    print("Recording to {} (Ctrl+C to stop)".format(args.out))
    start = time.monotonic()
    try:
        while not args.seconds or time.monotonic() - start < args.seconds:
            robot.keep_alive()
            time.sleep(0.5)
            print("\r{} samples".format(len(recorder.rows)), end="", flush=True)
    except KeyboardInterrupt:
        pass
    except (RobotError, OSError) as error:
        # Connection lost (robot restarted, out of range): keep what we have
        print("\n{}".format(error))
    robot.close()

    recorder.save(args.out)
    print("\nSaved {} samples to {}".format(len(recorder.rows), args.out))


if __name__ == "__main__":
    main()
