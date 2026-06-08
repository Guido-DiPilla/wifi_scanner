"""Unit tests for wifi_core.connection_service."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tests.conftest import make_command_result
from wifi_core.connection_service import (
    connect_to_network,
    connect_using_profile,
    disconnect_current_device,
)
from wifi_core.runner import CommandNotFoundError, CommandTimeoutError


class ConnectionServiceTests(unittest.TestCase):
    def test_connect_using_profile_success(self):
        runner = MagicMock()
        runner.run.return_value = make_command_result(returncode=0)

        result = connect_using_profile("HomeWiFi", runner=runner)

        self.assertEqual(result.returncode, 0)
        runner.run.assert_called_once_with(["nmcli", "connection", "up", "HomeWiFi"], timeout=30)

    def test_connect_to_network_includes_password(self):
        runner = MagicMock()
        runner.run.return_value = make_command_result(returncode=0)

        connect_to_network("HomeWiFi", "AA:BB:CC:DD:EE:FF", "secret", runner=runner)

        runner.run.assert_called_once_with(
            [
                "nmcli",
                "device",
                "wifi",
                "connect",
                "HomeWiFi",
                "password",
                "secret",
                "bssid",
                "AA:BB:CC:DD:EE:FF",
            ],
            timeout=30,
        )

    def test_connect_to_network_includes_device_when_provided(self):
        runner = MagicMock()
        runner.run.return_value = make_command_result(returncode=0)

        connect_to_network(
            "HomeWiFi",
            "AA:BB:CC:DD:EE:FF",
            "secret",
            device="wlan0",
            runner=runner,
        )

        runner.run.assert_called_once_with(
            [
                "nmcli",
                "device",
                "wifi",
                "connect",
                "HomeWiFi",
                "password",
                "secret",
                "ifname",
                "wlan0",
                "bssid",
                "AA:BB:CC:DD:EE:FF",
            ],
            timeout=30,
        )

    def test_connect_to_network_timeout_maps_to_runtime_error(self):
        runner = MagicMock()
        runner.run.side_effect = CommandTimeoutError("timeout")

        with self.assertRaises(RuntimeError) as ctx:
            connect_to_network("HomeWiFi", None, None, runner=runner)

        self.assertIn("timed out after 30 seconds", str(ctx.exception))

    def test_connect_using_profile_not_found_maps_to_runtime_error(self):
        runner = MagicMock()
        runner.run.side_effect = CommandNotFoundError("missing")

        with self.assertRaises(RuntimeError) as ctx:
            connect_using_profile("HomeWiFi", runner=runner)

        self.assertIn("nmcli not found", str(ctx.exception))

    def test_disconnect_uses_connected_wifi_device(self):
        runner = MagicMock()
        runner.run.side_effect = [
            make_command_result(stdout="wlan0:wifi:connected\neth0:ethernet:connected\n"),
            make_command_result(returncode=0),
        ]

        result = disconnect_current_device(runner=runner)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(runner.run.call_count, 2)
        first_call = runner.run.call_args_list[0]
        second_call = runner.run.call_args_list[1]
        self.assertEqual(
            first_call.kwargs,
            {"timeout": 5},
        )
        self.assertEqual(
            first_call.args[0],
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"],
        )
        self.assertEqual(
            second_call.args[0],
            ["nmcli", "device", "disconnect", "wlan0"],
        )
        self.assertEqual(second_call.kwargs, {"timeout": 10})

    def test_disconnect_raises_when_no_wifi_device_found(self):
        runner = MagicMock()
        runner.run.return_value = make_command_result(stdout="eth0:ethernet:connected\n")

        with self.assertRaises(RuntimeError) as ctx:
            disconnect_current_device(runner=runner)

        self.assertIn("No Wi-Fi device found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
