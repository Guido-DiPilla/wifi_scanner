"""Wi-Fi scan and saved password services."""

from __future__ import annotations

from collections import Counter
import time
import urllib.request

from wifi_core.models import WifiNetwork
from wifi_core.nmcli_parser import parse_scan_line
from wifi_core.runner import CommandNotFoundError, CommandRunner, CommandTimeoutError


_DEFAULT_RUNNER = CommandRunner()


def get_saved_password(ssid: str, runner: CommandRunner | None = None) -> str:
    if not ssid or ssid == "<hidden>":
        return ""

    active_runner = runner or _DEFAULT_RUNNER
    try:
        result = active_runner.run(
            ["nmcli", "-s", "-g", "802-11-wireless-security.psk", "connection", "show", ssid],
            timeout=2,
        )
    except (CommandNotFoundError, CommandTimeoutError):
        return ""

    password = result.stdout.strip()
    if password and password != "--":
        return password
    return ""


def get_device_ips(device: str, runner: CommandRunner | None = None) -> tuple[str, str]:
    """Return (ipv4, ipv6) CIDR addresses assigned to *device*. Empty string if unavailable."""
    if not device:
        return "", ""
    active_runner = runner or _DEFAULT_RUNNER

    def _fetch(field: str) -> str:
        try:
            result = active_runner.run(
                ["nmcli", "-g", field, "device", "show", device],
                timeout=2,
            )
        except (CommandNotFoundError, CommandTimeoutError):
            return ""
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and l.strip() != "--"]
        return lines[0] if lines else ""

    return _fetch("IP4.ADDRESS"), _fetch("IP6.ADDRESS")


def get_device_dns(device: str, runner: CommandRunner | None = None) -> tuple[str, str]:
    """Return (dns4, dns6) server lists for *device*, each as comma-separated string or empty."""
    if not device:
        return "", ""
    active_runner = runner or _DEFAULT_RUNNER

    def _fetch(field: str) -> str:
        try:
            result = active_runner.run(
                ["nmcli", "-g", field, "device", "show", device],
                timeout=2,
            )
        except (CommandNotFoundError, CommandTimeoutError):
            return ""
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and l.strip() != "--"]
        return ", ".join(lines) if lines else ""

    return _fetch("IP4.DNS"), _fetch("IP6.DNS")


def get_public_ip() -> str:
    """Return the public IPv4 address as seen from the internet, or empty string."""
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as resp:
            return resp.read().decode().strip()
    except Exception:
        return ""


def scan_wifi(runner: CommandRunner | None = None) -> list[WifiNetwork]:
    active_runner = runner or _DEFAULT_RUNNER
    try:
        result = active_runner.run(
            [
                "nmcli",
                "--terse",
                "--fields",
                "IN-USE,SSID,BSSID,MODE,CHAN,FREQ,RATE,SIGNAL,BARS,SECURITY,BANDWIDTH,DEVICE,WPA-FLAGS,RSN-FLAGS",
                "dev",
                "wifi",
                "list",
                "--rescan",
                "yes",
            ],
            timeout=15,
        )
    except CommandNotFoundError as exc:
        raise RuntimeError(
            "nmcli not found. Please install NetworkManager:\n"
            "  sudo apt install network-manager"
        ) from exc
    except CommandTimeoutError as exc:
        raise RuntimeError("Wi-Fi scan timed out. Is your Wi-Fi adapter enabled?") from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Unknown scan failure"
        raise RuntimeError(f"Wi-Fi scan failed: {detail}")

    current_time = time.time()
    networks: list[WifiNetwork] = []
    seen_bssids: set[str] = set()

    for line in result.stdout.splitlines():
        net = parse_scan_line(line, current_time)
        if net is None:
            continue
        if net.bssid in seen_bssids:
            continue
        seen_bssids.add(net.bssid)
        networks.append(net)

    channel_counts = Counter(n.channel for n in networks)
    for net in networks:
        net.congestion = channel_counts[net.channel]

    networks.sort(key=lambda n: (not n.in_use, -n.signal))
    return networks
