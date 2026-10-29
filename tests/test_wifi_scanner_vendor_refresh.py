"""Unit tests for background vendor database refresh behavior."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from wifi_scanner import WifiScannerApp


class WifiScannerVendorRefreshTests(unittest.TestCase):
    def test_start_vendor_db_refresh_runs_once_while_in_flight(self):
        app = WifiScannerApp.__new__(WifiScannerApp)
        app._vendor_refresh_in_flight = False
        app._start_background_task = MagicMock()

        app._start_vendor_db_refresh()
        app._start_vendor_db_refresh()

        app._start_background_task.assert_called_once()
        self.assertTrue(app._vendor_refresh_in_flight)

    def test_refresh_vendor_db_async_success_reloads_and_posts_ui_callback(self):
        app = WifiScannerApp.__new__(WifiScannerApp)
        app.after = MagicMock()

        with patch("wifi_scanner.refresh_authoritative_ieee_cache", return_value=True) as refresh_mock, \
             patch("wifi_scanner.reload_vendor_database") as reload_mock:
            app._refresh_vendor_db_async()

        refresh_mock.assert_called_once_with(force=True, timeout=30.0)
        reload_mock.assert_called_once_with(force_refresh=False)
        app.after.assert_called_once_with(0, app._on_vendor_db_refresh_complete, True)

    def test_refresh_vendor_db_async_failure_keeps_existing_mappings(self):
        app = WifiScannerApp.__new__(WifiScannerApp)
        app.after = MagicMock()

        with patch("wifi_scanner.refresh_authoritative_ieee_cache", side_effect=OSError("offline")) as refresh_mock, \
             patch("wifi_scanner.reload_vendor_database") as reload_mock:
            app._refresh_vendor_db_async()

        refresh_mock.assert_called_once_with(force=True, timeout=30.0)
        reload_mock.assert_not_called()
        app.after.assert_called_once_with(0, app._on_vendor_db_refresh_complete, False)

    def test_on_vendor_db_refresh_complete_success_invalidate_and_rerender(self):
        app = WifiScannerApp.__new__(WifiScannerApp)

        class DummyNetwork:
            pass

        net = DummyNetwork()
        net.vendor = "Old Vendor"

        app._vendor_refresh_in_flight = True
        app._networks = [net]
        app._render_list = MagicMock()
        app._refresh_selected_network_details = MagicMock()
        app._update_filter_status = MagicMock()

        app._on_vendor_db_refresh_complete(True)

        self.assertFalse(app._vendor_refresh_in_flight)
        self.assertNotIn("vendor", net.__dict__)
        app._render_list.assert_called_once_with()
        app._refresh_selected_network_details.assert_called_once_with([net])
        app._update_filter_status.assert_called_once_with()

    def test_on_vendor_db_refresh_complete_failure_is_noop(self):
        app = WifiScannerApp.__new__(WifiScannerApp)

        class DummyNetwork:
            pass

        net = DummyNetwork()
        net.vendor = "Old Vendor"

        app._vendor_refresh_in_flight = True
        app._networks = [net]
        app._render_list = MagicMock()
        app._refresh_selected_network_details = MagicMock()
        app._update_filter_status = MagicMock()

        app._on_vendor_db_refresh_complete(False)

        self.assertFalse(app._vendor_refresh_in_flight)
        self.assertEqual(net.vendor, "Old Vendor")
        app._render_list.assert_not_called()
        app._refresh_selected_network_details.assert_not_called()
        app._update_filter_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
