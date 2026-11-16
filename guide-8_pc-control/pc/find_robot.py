# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Find RW-1 robots: by name, on the access point and on your home network.

    python find_robot.py              # look for rw-1.local, 192.168.4.1, then scan
    python find_robot.py --name bob   # the robot was renamed to bob

The scan asks every address of your PC's network (x.x.x.1 to x.x.x.254)
for /api/info, 64 at a time; it takes a few seconds.
"""
import argparse
import ipaddress
import json
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def ask(host, timeout=1.0):
    """The robot's /api/info at host, or None."""
    try:
        with urllib.request.urlopen("http://{}/api/info".format(host), timeout=timeout) as reply:
            info = json.loads(reply.read())
        return info if "telemetry_fields" in info else None
    except (OSError, ValueError):
        return None


def my_address():
    """This PC's address on the network it uses to reach the outside world."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))      # no packet is sent
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


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

    found = {}
    for host in (args.name + ".local", "192.168.4.1"):
        info = ask(host, timeout=2.0)
        if info:
            found[info["wifi"]["ap"]["ssid"]] = (host, info)

    me = my_address()
    if me and not me.startswith("192.168.4."):
        net = ipaddress.ip_network(me + "/24", strict=False)
        print("Scanning {} ...".format(net))
        hosts = [str(h) for h in net.hosts() if str(h) != me]
        with ThreadPoolExecutor(max_workers=64) as pool:
            for host, info in zip(hosts, pool.map(ask, hosts)):
                if info and info["wifi"]["ap"]["ssid"] not in found:
                    found[info["wifi"]["ap"]["ssid"]] = (host, info)

    if not found:
        print("No robot found. Is it switched on? Join its network RW-1-XXXX and try again.")
    for host, info in found.values():
        show(host, info)


if __name__ == "__main__":
    main()
