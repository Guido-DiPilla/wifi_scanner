"""
tests/test_scanner_service.py — Unit tests for wifi_core.scanner_service.

Uses a mock CommandRunner so no real nmcli is needed.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from wifi_core.runner import CommandNotFoundError, CommandResult, CommandTimeoutError
from wifi_core.scanner_service import get_device_dns, get_device_ips, get_public_ip, get_saved_password, scan_wifi



def _make_runner(stdout="", stderr="", returncode=0):
    """Return a mock CommandRunner whose run() returns a fixed CommandResult."""
    runner = MagicMock()
    runner.run.return_value = CommandResult(
        stdout=stdout, stderr=stderr, returncode=returncode
    )
    return runner


class TestGetSavedPassword(unittest.TestCase):
    def test_returns_password_when_found(self):
        # nmcli -s -g returns just the field value, not the full property name
        runner = _make_runner(stdout="s3cr3t")
        self.assertEqual(get_saved_password("MyNet", runner=runner), "s3cr3t")

    def test_returns_empty_string_when_not_saved(self):
        runner = _make_runner(returncode=10, stderr="No such connection")
        self.assertEqual(get_saved_password("Unknown", runner=runner), "")

    def test_returns_empty_string_when_psk_is_dash(self):
        # nmcli returns "--" when the field has no value
        runner = _make_runner(stdout="--")
        self.assertEqual(get_saved_password("MyNet", runner=runner), "")

    def test_hidden_ssid_short_circuits_without_runner_call(self):
        runner = MagicMock()
        self.assertEqual(get_saved_password("<hidden>", runner=runner), "")
        runner.run.assert_not_called()


class TestScanWifi(unittest.TestCase):
    # One valid nmcli scan line — fields match the --fields order used in scan_wifi:
    # IN-USE:SSID:BSSID:MODE:CHAN:FREQ:RATE:SIGNAL:BARS:SECURITY:BANDWIDTH:DEVICE:WPA-FLAGS:RSN-FLAGS
    # BSSID colons must be escaped with backslash in nmcli --terse output.
    _NMCLI_LINE = (
        r"*:MySSID:AA\:BB\:CC\:DD\:EE\:FF:Infra:6:2437 MHz:130 Mbit/s:85:"
        r"\u25b2\u25b2\u25b2\u25b2:WPA2:40 MHz:wlan0:pair_ccmp:pair_ccmp" + "\n"
    )

    def test_returns_list_of_networks(self):
        runner = _make_runner(stdout=self._NMCLI_LINE)
        networks = scan_wifi(runner=runner)
        self.assertIsInstance(networks, list)
        self.assertGreater(len(networks), 0)

    def test_network_ssid_is_parsed(self):
        runner = _make_runner(stdout=self._NMCLI_LINE)
        networks = scan_wifi(runner=runner)
        self.assertEqual(networks[0].ssid, "MySSID")

    def test_connected_network_is_first(self):
        runner = _make_runner(stdout=self._NMCLI_LINE)
        networks = scan_wifi(runner=runner)
        self.assertTrue(networks[0].in_use)

    def test_connected_network_sorts_before_stronger_unconnected(self):
        connected_weak = (
            r"*:Conn:AA\:BB\:CC\:DD\:EE\:01:Infra:6:2437 MHz:130 Mbit/s:30:****:WPA2:40 MHz:wlan0:::"
        )
        unconnected_strong = (
            r":Strong:AA\:BB\:CC\:DD\:EE\:02:Infra:36:5180 MHz:866 Mbit/s:95:****:WPA2:80 MHz:wlan0:::"
        )
        runner = _make_runner(stdout="\n".join([unconnected_strong, connected_weak]))

        networks = scan_wifi(runner=runner)

        self.assertEqual(networks[0].ssid, "Conn")
        self.assertTrue(networks[0].in_use)

    def test_empty_ssid_is_normalized_to_hidden(self):
        hidden_line = (
            r": :AA\:BB\:CC\:DD\:EE\:10:Infra:1:2412 MHz:65 Mbit/s:40:**:WPA2:20 MHz:wlan0:::"
        )
        # truly empty SSID field between the first and second separators
        hidden_line = hidden_line.replace(": :", "::", 1)
        runner = _make_runner(stdout=hidden_line)

        networks = scan_wifi(runner=runner)

        self.assertEqual(len(networks), 1)
        self.assertEqual(networks[0].ssid, "<hidden>")

    def test_empty_output_returns_empty_list(self):
        runner = _make_runner(stdout="")
        networks = scan_wifi(runner=runner)
        self.assertEqual(networks, [])

    def test_non_zero_returncode_raises(self):
        runner = _make_runner(returncode=1, stderr="nmcli: not found")
        with self.assertRaises(RuntimeError):
            scan_wifi(runner=runner)

    def test_deduplicates_by_bssid_and_sets_congestion(self):
        line_a = (
            r"*:A:AA\:BB\:CC\:DD\:EE\:FF:Infra:6:2437 MHz:130 Mbit/s:80:****:WPA2:40 MHz:wlan0:::"
        )
        line_a_dupe = (
            r":A-dup:AA\:BB\:CC\:DD\:EE\:FF:Infra:6:2437 MHz:130 Mbit/s:70:****:WPA2:40 MHz:wlan0:::"
        )
        line_b = (
            r":B:11\:22\:33\:44\:55\:66:Infra:6:2437 MHz:130 Mbit/s:60:****:WPA2:40 MHz:wlan0:::"
        )
        runner = _make_runner(stdout="\n".join([line_a, line_a_dupe, line_b]))

        networks = scan_wifi(runner=runner)

        self.assertEqual(len(networks), 2)
        for n in networks:
            self.assertEqual(n.congestion, 2)

    def test_command_not_found_raises_runtime_error(self):
        runner = MagicMock()
        runner.run.side_effect = CommandNotFoundError("missing")
        with self.assertRaises(RuntimeError):
            scan_wifi(runner=runner)

    def test_scan_timeout_raises_runtime_error(self):
        runner = MagicMock()
        runner.run.side_effect = CommandTimeoutError("timeout")
        with self.assertRaises(RuntimeError):
            scan_wifi(runner=runner)

    def test_scan_wifi_skips_malformed_lines(self):
        # A line with too few fields parses to None and must be silently skipped
        good_line = (
            r":MySSID:AA\:BB\:CC\:DD\:EE\:FF:Infra:6:2437 MHz:130 Mbit/s:85:****:WPA2:40 MHz:wlan0::"
        )
        runner = _make_runner(stdout="too:short\n" + good_line)
        networks = scan_wifi(runner=runner)
        self.assertEqual(len(networks), 1)
        self.assertEqual(networks[0].ssid, "MySSID")


class TestGetSavedPasswordErrors(unittest.TestCase):
    def test_command_not_found_returns_empty_string(self):
        runner = MagicMock()
        runner.run.side_effect = CommandNotFoundError("nmcli not found")
        self.assertEqual(get_saved_password("MyNet", runner=runner), "")

    def test_command_timeout_returns_empty_string(self):
        runner = MagicMock()
        runner.run.side_effect = CommandTimeoutError("timed out")
        self.assertEqual(get_saved_password("MyNet", runner=runner), "")


class TestGetDeviceIps(unittest.TestCase):
    def test_returns_ipv4_and_ipv6_when_both_available(self):
        runner = MagicMock()
        runner.run.side_effect = [
            CommandResult(stdout="192.168.1.42/24", stderr="", returncode=0),
            CommandResult(stdout="fe80::abcd:1234/64", stderr="", returncode=0),
        ]
        ipv4, ipv6 = get_device_ips("wlan0", runner=runner)
        self.assertEqual(ipv4, "192.168.1.42/24")
        self.assertEqual(ipv6, "fe80::abcd:1234/64")

    def test_empty_device_returns_empty_strings_without_calling_runner(self):
        runner = MagicMock()
        ipv4, ipv6 = get_device_ips("", runner=runner)
        self.assertEqual(ipv4, "")
        self.assertEqual(ipv6, "")
        runner.run.assert_not_called()

    def test_dash_result_returns_empty_string(self):
        runner = MagicMock()
        runner.run.side_effect = [
            CommandResult(stdout="--", stderr="", returncode=0),
            CommandResult(stdout="--", stderr="", returncode=0),
        ]
        ipv4, ipv6 = get_device_ips("wlan0", runner=runner)
        self.assertEqual(ipv4, "")
        self.assertEqual(ipv6, "")

    def test_command_not_found_returns_empty_strings(self):
        runner = MagicMock()
        runner.run.side_effect = CommandNotFoundError("nmcli not found")
        ipv4, ipv6 = get_device_ips("wlan0", runner=runner)
        self.assertEqual(ipv4, "")
        self.assertEqual(ipv6, "")

    def test_command_timeout_returns_empty_strings(self):
        runner = MagicMock()
        runner.run.side_effect = CommandTimeoutError("timed out")
        ipv4, ipv6 = get_device_ips("wlan0", runner=runner)
        self.assertEqual(ipv4, "")
        self.assertEqual(ipv6, "")

    def test_multiple_ipv6_addresses_uses_first_line(self):
        runner = MagicMock()
        runner.run.side_effect = [
            CommandResult(stdout="192.168.1.42/24", stderr="", returncode=0),
            CommandResult(
                stdout="2001:db8::1/64\nfe80::abcd:1234/64", stderr="", returncode=0
            ),
        ]
        ipv4, ipv6 = get_device_ips("wlan0", runner=runner)
        self.assertEqual(ipv4, "192.168.1.42/24")
        self.assertEqual(ipv6, "2001:db8::1/64")


class TestGetDeviceDns(unittest.TestCase):
    def test_returns_dns4_and_dns6_when_both_available(self):
        runner = MagicMock()
        runner.run.side_effect = [
            CommandResult(stdout="8.8.8.8\n8.8.4.4", stderr="", returncode=0),
            CommandResult(stdout="2001:4860:4860::8888", stderr="", returncode=0),
        ]
        dns4, dns6 = get_device_dns("wlan0", runner=runner)
        self.assertEqual(dns4, "8.8.8.8, 8.8.4.4")
        self.assertEqual(dns6, "2001:4860:4860::8888")

    def test_empty_device_returns_empty_strings_without_calling_runner(self):
        runner = MagicMock()
        dns4, dns6 = get_device_dns("", runner=runner)
        self.assertEqual(dns4, "")
        self.assertEqual(dns6, "")
        runner.run.assert_not_called()

    def test_dash_result_returns_empty_string(self):
        runner = MagicMock()
        runner.run.side_effect = [
            CommandResult(stdout="--", stderr="", returncode=0),
            CommandResult(stdout="--", stderr="", returncode=0),
        ]
        dns4, dns6 = get_device_dns("wlan0", runner=runner)
        self.assertEqual(dns4, "")
        self.assertEqual(dns6, "")

    def test_command_not_found_returns_empty_strings(self):
        runner = MagicMock()
        runner.run.side_effect = CommandNotFoundError("nmcli not found")
        dns4, dns6 = get_device_dns("wlan0", runner=runner)
        self.assertEqual(dns4, "")
        self.assertEqual(dns6, "")

    def test_command_timeout_returns_empty_strings(self):
        runner = MagicMock()
        runner.run.side_effect = CommandTimeoutError("timed out")
        dns4, dns6 = get_device_dns("wlan0", runner=runner)
        self.assertEqual(dns4, "")
        self.assertEqual(dns6, "")


class TestGetPublicIp(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_returns_ip_on_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"203.0.113.42"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        self.assertEqual(get_public_ip(), "203.0.113.42")

    @patch("urllib.request.urlopen")
    def test_returns_empty_string_on_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("network error")
        self.assertEqual(get_public_ip(), "")

    @patch("urllib.request.urlopen")
    def test_strips_whitespace_from_response(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"  203.0.113.42\n"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        self.assertEqual(get_public_ip(), "203.0.113.42")


if __name__ == "__main__":
    unittest.main()
