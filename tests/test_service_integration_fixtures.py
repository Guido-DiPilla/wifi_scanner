"""Integration-style service tests using realistic nmcli output fixtures."""

from __future__ import annotations

import unittest
from pathlib import Path

from wifi_core.connection_service import disconnect_current_device
from wifi_core.runner import CommandResult
from wifi_core.scanner_service import get_device_dns, get_device_ips, scan_wifi


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "nmcli"


def _fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class FixtureRunner:
    """CommandRunner stub backed by argv-to-result mappings."""

    def __init__(self, responses: dict[tuple[str, ...], CommandResult]):
        self._responses = responses
        self.calls: list[tuple[list[str], int]] = []

    def run(self, argv: list[str], timeout: int) -> CommandResult:
        self.calls.append((list(argv), timeout))
        key = tuple(argv)
        if key not in self._responses:
            raise AssertionError(f"Unexpected command: {argv}")
        return self._responses[key]


class ServiceIntegrationFixtureTests(unittest.TestCase):
    def test_scan_wifi_with_realistic_fixture_output(self):
        scan_cmd = (
            "nmcli",
            "--terse",
            "--fields",
            "IN-USE,SSID,BSSID,MODE,CHAN,FREQ,RATE,SIGNAL,BARS,SECURITY,BANDWIDTH,DEVICE,WPA-FLAGS,RSN-FLAGS",
            "dev",
            "wifi",
            "list",
            "--rescan",
            "yes",
        )
        runner = FixtureRunner(
            {
                scan_cmd: CommandResult(
                    returncode=0,
                    stdout=_fixture_text("scan_mixed.txt"),
                    stderr="",
                ),
            }
        )

        networks = scan_wifi(runner=runner)

        self.assertEqual(len(networks), 3)
        # Connected network is always sorted first by scan service.
        self.assertEqual(networks[0].ssid, "CafeWiFi")
        self.assertTrue(networks[0].in_use)

        by_bssid = {n.bssid: n for n in networks}
        self.assertEqual(by_bssid["AA:BB:CC:DD:EE:01"].signal, 45)
        self.assertEqual(by_bssid["AA:BB:CC:DD:EE:01"].congestion, 2)
        self.assertEqual(by_bssid["AA:BB:CC:DD:EE:02"].congestion, 2)
        self.assertEqual(by_bssid["AA:BB:CC:DD:EE:03"].congestion, 1)

        self.assertEqual(runner.calls[0][0], list(scan_cmd))
        self.assertEqual(runner.calls[0][1], 15)

    def test_disconnect_current_device_uses_active_wifi_from_fixture(self):
        status_cmd = (
            "nmcli",
            "-t",
            "-f",
            "DEVICE,TYPE,STATE",
            "device",
            "status",
        )
        disconnect_cmd = ("nmcli", "device", "disconnect", "wlp2s0")
        runner = FixtureRunner(
            {
                status_cmd: CommandResult(
                    returncode=0,
                    stdout=_fixture_text("device_status_mixed.txt"),
                    stderr="",
                ),
                disconnect_cmd: CommandResult(returncode=0, stdout="", stderr=""),
            }
        )

        result = disconnect_current_device(runner=runner)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(runner.calls[0], (list(status_cmd), 5))
        self.assertEqual(runner.calls[1], (list(disconnect_cmd), 10))

    def test_ip_and_dns_extraction_from_fixture_outputs(self):
        device = "wlan0"
        runner = FixtureRunner(
            {
                ("nmcli", "-g", "IP4.ADDRESS", "device", "show", device): CommandResult(
                    returncode=0,
                    stdout=_fixture_text("device_ip4_show.txt"),
                    stderr="",
                ),
                ("nmcli", "-g", "IP6.ADDRESS", "device", "show", device): CommandResult(
                    returncode=0,
                    stdout=_fixture_text("device_ip6_show.txt"),
                    stderr="",
                ),
                ("nmcli", "-g", "IP4.DNS", "device", "show", device): CommandResult(
                    returncode=0,
                    stdout=_fixture_text("device_dns4_show.txt"),
                    stderr="",
                ),
                ("nmcli", "-g", "IP6.DNS", "device", "show", device): CommandResult(
                    returncode=0,
                    stdout=_fixture_text("device_dns6_show.txt"),
                    stderr="",
                ),
            }
        )

        ipv4, ipv6 = get_device_ips(device, runner=runner)
        dns4, dns6 = get_device_dns(device, runner=runner)

        self.assertEqual(ipv4, "192.168.1.8/24")
        self.assertEqual(ipv6, "fe80::1234:abcd/64")
        self.assertEqual(dns4, "1.1.1.1, 8.8.8.8")
        self.assertEqual(dns6, "2001:4860:4860::8888")


if __name__ == "__main__":
    unittest.main()
