"""Unit tests for Wi-Fi scanner connection target selection."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from wifi_core.models import WifiNetwork
from wifi_scanner import WifiScannerApp, should_disconnect_before_targeted_connect


class WifiScannerConnectSelectionTests(unittest.TestCase):
    def _net(self, **overrides) -> WifiNetwork:
        base = {
            "ssid": "HomeWiFi",
            "bssid": "AA:BB:CC:DD:EE:FF",
            "mode": "Infra",
            "channel": "36",
            "frequency": "5180 MHz",
            "rate": "600 Mbit/s",
            "signal": 72,
            "bars": "▂▄▆_",
            "security": "WPA2",
        }
        base.update(overrides)
        return WifiNetwork(**base)

    def test_saved_password_prefers_direct_bssid_connect(self):
        app = WifiScannerApp.__new__(WifiScannerApp)
        app._do_connect = MagicMock()
        app._show_password_dialog = MagicMock()

        app._on_saved_password_lookup(self._net(), "secret-pass")

        app._do_connect.assert_called_once_with("HomeWiFi", "AA:BB:CC:DD:EE:FF", "secret-pass", None)
        app._show_password_dialog.assert_not_called()

    def test_secured_network_without_saved_password_prompts(self):
        app = WifiScannerApp.__new__(WifiScannerApp)
        app._do_connect = MagicMock()
        app._show_password_dialog = MagicMock()
        net = self._net(security="WPA3")

        app._on_saved_password_lookup(net, "")

        app._show_password_dialog.assert_called_once_with(net)
        app._do_connect.assert_not_called()

    def test_open_network_without_saved_password_connects_directly(self):
        app = WifiScannerApp.__new__(WifiScannerApp)
        app._do_connect = MagicMock()
        app._show_password_dialog = MagicMock()
        net = self._net(security="Open")

        app._on_saved_password_lookup(net, "")

        app._do_connect.assert_called_once_with("HomeWiFi", "AA:BB:CC:DD:EE:FF", None, None)
        app._show_password_dialog.assert_not_called()


class WifiScannerConnectHandoffTests(unittest.TestCase):
    def test_handoff_not_required_without_current_bssid(self):
        self.assertFalse(
            should_disconnect_before_targeted_connect(None, "AA:BB:CC:DD:EE:FF")
        )

    def test_handoff_not_required_without_target_bssid(self):
        self.assertFalse(
            should_disconnect_before_targeted_connect("AA:BB:CC:DD:EE:01", None)
        )

    def test_handoff_not_required_when_same_bssid(self):
        self.assertFalse(
            should_disconnect_before_targeted_connect(
                "AA:BB:CC:DD:EE:FF",
                "AA:BB:CC:DD:EE:FF",
            )
        )

    def test_handoff_required_for_different_target_bssid(self):
        self.assertTrue(
            should_disconnect_before_targeted_connect(
                "AA:BB:CC:DD:EE:01",
                "AA:BB:CC:DD:EE:FF",
            )
        )


if __name__ == "__main__":
    unittest.main()
