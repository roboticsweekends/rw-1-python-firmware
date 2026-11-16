# SPDX-FileCopyrightText: 2026 Robotics Weekends
# SPDX-License-Identifier: MIT
"""
Wi-Fi of the Wi-Fi board: the robot's own access point, always on, plus an
optional connection to the home network (client mode).

  Access point  - network RW-1-XXXX (XXXX from the board's MAC address),
                  page at http://192.168.4.1. Always running, so the robot
                  can be reached even when the home network has problems.
  Client        - connects to the home network if one is set up. The robot
                  is then also reachable at http://<ROBOT_NAME>.local and at
                  the IP address the router gives it.

The ESP32 has one radio, so the access point works on the home network's
channel. Phones connected to the access point may reconnect once when the
robot joins the home network.

While the home network is gone, the radio keeps scanning for it, which
disturbs the access point. So after CLIENT_GIVE_UP_S seconds without the
home network, the robot stops looking and tries again every
CLIENT_RETRY_S seconds, only while the robot isn't being driven.

Settings come from settings.toml (ROBOT_NAME, AP_SSID, AP_PASSWORD,
WIFI_SSID, WIFI_PASSWORD) and are replaced by the ones saved from the web
page (lib/store.py, section "wifi").
"""
import ipaddress
import os
import time

import wifi

import store

AP_IP = "192.168.4.1"
CONNECT_TIMEOUT_S = 15     # how long to try joining the home network
CLIENT_GIVE_UP_S = 30      # home network lost this long: stop looking for it
CLIENT_RETRY_S = 300       # then look again this often
NS_PER_S = 1_000_000_000


def _setting(key, default=""):
    try:
        value = os.getenv(key)
    except (ValueError, SyntaxError):
        value = None
    return default if value is None else str(value)


def check_password(password):
    """Return an error message, or None if the password is valid for WPA2."""
    if password and not 8 <= len(password) <= 63:
        return "the password must be 8 to 63 characters, or empty for an open network"
    return None


class WifiSetup:
    def __init__(self):
        radio = wifi.radio
        self.radio = radio
        mac = bytes(radio.mac_address)
        suffix = "{:02X}{:02X}".format(mac[-2], mac[-1])

        saved = store.load("wifi")
        self.name = saved.get("name") or _setting("ROBOT_NAME", "rw-1")
        self.ap_ssid = saved.get("ap_ssid") or _setting("AP_SSID") or "RW-1-" + suffix
        self.ap_password = saved.get("ap_password", _setting("AP_PASSWORD", "rw1robot"))
        self.ssid = saved.get("ssid", _setting("WIFI_SSID"))
        self.password = saved.get("password", _setting("WIFI_PASSWORD"))

        self.mdns = None
        self.client_state = "off"    # off, connected, lost, paused, failed
        self._lost_since = None
        self._next_retry = None
        self.last_test = {}          # result of the last test(): ssid, ok, ip or error

    # --- start -------------------------------------------------------------

    def start(self):
        """Join the home network (if set up), then start the access point and mDNS."""
        radio = self.radio
        radio.hostname = self.name
        if self.ssid:
            print("Joining", self.ssid, "...")
            self._connect(self.ssid, self.password)
            print("Home network:", self.client_state, self.ip_client() or "")
        self._start_ap()
        print("Access point: {} at http://{}".format(self.ap_ssid, AP_IP))
        self._start_mdns()

    def _start_ap(self):
        radio = self.radio
        # Set the address before starting the access point: it's then used
        # from the first client on
        radio.set_ipv4_address_ap(
            ipv4=ipaddress.IPv4Address(AP_IP),
            netmask=ipaddress.IPv4Address("255.255.255.0"),
            gateway=ipaddress.IPv4Address(AP_IP),
        )
        # With the home network connected, the access point must use its channel
        channel = radio.ap_info.channel if radio.connected and radio.ap_info else 1
        radio.start_ap(self.ap_ssid, self.ap_password, channel=channel)
        # The address may take a moment to appear
        for _ in range(50):
            if radio.ipv4_address_ap is not None:
                break
            time.sleep(0.1)

    def _start_mdns(self):
        try:
            import mdns
            self.mdns = mdns.Server(self.radio)
            self.mdns.hostname = self.name
            self.mdns.advertise_service(service_type="_http", protocol="_tcp", port=80)
            print("Also at http://{}.local".format(self.name))
        except (ImportError, RuntimeError, OSError) as error:
            print("mDNS not available:", error)

    def _connect(self, ssid, password):
        """Try to join a network. Blocks up to CONNECT_TIMEOUT_S. Return an error or None."""
        radio = self.radio
        try:
            radio.start_station()
            radio.connect(ssid, password, timeout=CONNECT_TIMEOUT_S)
        except (ConnectionError, OSError, RuntimeError) as error:
            radio.stop_station()
            self.client_state = "failed"
            return str(error) or "could not connect"
        self.client_state = "connected"
        self._lost_since = None
        return None

    # --- running -----------------------------------------------------------

    def update(self, busy):
        """
        Call often. Watches the home network connection and retries it.

        :param bool busy: True while the robot is being driven: a retry
            blocks the loop for up to CONNECT_TIMEOUT_S, so it waits.
        """
        if not self.ssid:
            self.client_state = "off"
            return
        now = time.monotonic_ns()
        connected = self.radio.connected
        if self.client_state == "connected" and not connected:
            self.client_state = "lost"
            self._lost_since = now
            print("Home network lost")
        elif self.client_state == "lost":
            if connected:
                self.client_state = "connected"
                print("Home network back:", self.ip_client())
            elif now - self._lost_since > CLIENT_GIVE_UP_S * NS_PER_S:
                # Stop scanning, so the access point stays stable
                self.radio.stop_station()
                self.client_state = "paused"
                self._next_retry = now + CLIENT_RETRY_S * NS_PER_S
                print("Home network: stopped looking, retry in", CLIENT_RETRY_S, "s")
        elif self.client_state in ("paused", "failed"):
            if self._next_retry is None:
                self._next_retry = now + CLIENT_RETRY_S * NS_PER_S
            elif now >= self._next_retry and not busy:
                self.reconnect()

    def reconnect(self):
        """Try the home network now. Blocks up to CONNECT_TIMEOUT_S."""
        if not self.ssid:
            return "no home network set up"
        error = self._connect(self.ssid, self.password)
        self._next_retry = None if error is None else (
            time.monotonic_ns() + CLIENT_RETRY_S * NS_PER_S)
        return error

    # --- set-up from the web page --------------------------------------------

    def scan(self):
        """List the networks in range: [{ssid, rssi, channel, open}], strongest first."""
        radio = self.radio
        if not radio.connected:
            radio.start_station()
        found = {}
        for net in radio.start_scanning_networks():
            if net.ssid and (net.ssid not in found or net.rssi > found[net.ssid]["rssi"]):
                found[net.ssid] = {
                    "ssid": net.ssid,
                    "rssi": net.rssi,
                    "channel": net.channel,
                    "open": wifi.AuthMode.OPEN in net.authmode,
                }
        radio.stop_scanning_networks()
        return sorted(found.values(), key=lambda n: -n["rssi"])

    def test(self, ssid, password):
        """
        Try to join a network without saving it. The result is also kept in
        last_test, because the phone that asked may lose its connection to
        the access point while the channel changes, and can ask again.
        """
        error = check_password(password) if password else None
        if error is None:
            error = self._connect(ssid, password)
        if error is None:
            self.last_test = {"ssid": ssid, "ok": True, "ip": self.ip_client()}
        else:
            self.last_test = {"ssid": ssid, "ok": False, "error": error}
            # Go back to the saved home network, if there is one
            if self.ssid and self.ssid != ssid:
                self.reconnect()
        return self.last_test

    def save_client(self, ssid, password):
        """Save the home network to join on the next start (empty ssid = none)."""
        if ssid:
            error = check_password(password)
            if error:
                return error
        saved = store.load("wifi")
        saved["ssid"] = ssid
        saved["password"] = password if ssid else ""
        store.save(saved, "wifi")
        return None

    def save_ap(self, ap_ssid, ap_password):
        """Save the access point's name and password for the next start."""
        if not ap_ssid or len(ap_ssid) > 32:
            return "the network name must be 1 to 32 characters"
        error = check_password(ap_password)
        if error:
            return error
        saved = store.load("wifi")
        saved["ap_ssid"] = ap_ssid
        saved["ap_password"] = ap_password
        store.save(saved, "wifi")
        return None

    def save_name(self, name):
        """Save the robot's name (used as <name>.local) for the next start."""
        ok = name and len(name) <= 32 and all(c.isalpha() or c.isdigit() or c == "-" for c in name)
        if not ok:
            return "the name may use letters, digits and '-', 1 to 32 characters"
        saved = store.load("wifi")
        saved["name"] = name.lower()
        store.save(saved, "wifi")
        return None

    @staticmethod
    def forget():
        """Forget everything saved from the web page about Wi-Fi."""
        store.clear("wifi")

    # --- state -----------------------------------------------------------

    def ip_client(self):
        ip = self.radio.ipv4_address
        return str(ip) if ip is not None else None

    def info(self):
        """Wi-Fi state for the web page (no passwords)."""
        ap_info = self.radio.ap_info if self.radio.connected else None
        return {
            "name": self.name,
            "hostname": self.name + ".local",
            "ap": {
                "ssid": self.ap_ssid,
                "ip": AP_IP,
                "open": not self.ap_password,
                "default_password": self.ap_password == "rw1robot",
            },
            "client": {
                "ssid": self.ssid,
                "state": self.client_state,
                "ip": self.ip_client(),
                "rssi": ap_info.rssi if ap_info else None,
                "channel": ap_info.channel if ap_info else None,
            },
            "last_test": self.last_test,
        }
