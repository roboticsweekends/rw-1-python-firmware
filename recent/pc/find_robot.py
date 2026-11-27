# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Find RW-1 robots: by name, on the access point and on your home network.

    python find_robot.py --name rw-1
"""
import argparse

from rw1_client import find_robots


def show(host, info):
    wifi = info["wifi"]
    print("Found {} at http://{}".format(info["name"], host))
    print("  access point {} (http://{})".format(wifi["ap"]["ssid"], wifi["ap"]["ip"]))
    if wifi["client"]["ip"]:
        print("  home network {}: http://{}".format(wifi["client"]["ssid"], wifi["client"]["ip"]))
    print("  name: http://{}".format(wifi["hostname"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--name", default="rw-1", help="robot name (default rw-1)")
    args = parser.parse_args()

    robots = find_robots(args.name, on_scan=lambda net: print("Scanning {} ...".format(net)))
    if not robots:
        print("No robot found. Is it switched on? Join its network RW-1-XXXX and try again.")
    for host, info in robots:
        show(host, info)


if __name__ == "__main__":
    main()
