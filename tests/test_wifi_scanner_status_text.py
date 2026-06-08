"""Unit tests for Wi-Fi scanner status text formatting helpers."""

from __future__ import annotations

import unittest

from wifi_scanner import (
    format_countdown_status,
    format_filter_status,
    format_found_count_status,
    scan_watchdog_timed_out,
)


class WifiScannerStatusTextTests(unittest.TestCase):
    def test_found_count_status_handles_singular(self):
        self.assertEqual(format_found_count_status(1), "1 network found")

    def test_found_count_status_handles_plural(self):
        self.assertEqual(format_found_count_status(2), "2 networks found")

    def test_filter_status_without_query_falls_back_to_found_count(self):
        self.assertEqual(
            format_filter_status(total=5, visible=5, query="  "),
            "5 networks found",
        )

    def test_filter_status_with_query_uses_visible_and_total(self):
        self.assertEqual(
            format_filter_status(total=12, visible=3, query="home"),
            'Showing 3 of 12 for "home"',
        )

    def test_filter_status_trims_query_whitespace(self):
        self.assertEqual(
            format_filter_status(total=9, visible=1, query="  office  "),
            'Showing 1 of 9 for "office"',
        )

    def test_countdown_status_without_query(self):
        self.assertEqual(
            format_countdown_status(total=4, visible=4, query="", remaining=9),
            "4 networks · next scan in 9s",
        )

    def test_countdown_status_with_query(self):
        self.assertEqual(
            format_countdown_status(total=10, visible=2, query="guest", remaining=5),
            'Showing 2 of 10 for "guest" · next scan in 5s',
        )

    def test_countdown_status_uses_singular_wording(self):
        self.assertEqual(
            format_countdown_status(total=1, visible=1, query="", remaining=7),
            "1 network · next scan in 7s",
        )

    def test_countdown_status_trims_query_whitespace(self):
        self.assertEqual(
            format_countdown_status(total=8, visible=3, query="  cafe  ", remaining=4),
            'Showing 3 of 8 for "cafe" · next scan in 4s',
        )

    def test_countdown_status_keeps_filter_status_prefix(self):
        filter_text = format_filter_status(total=11, visible=4, query="office")
        countdown_text = format_countdown_status(total=11, visible=4, query="office", remaining=6)
        self.assertTrue(countdown_text.startswith(filter_text))
        self.assertEqual(countdown_text, 'Showing 4 of 11 for "office" · next scan in 6s')

    def test_scan_watchdog_timeout_returns_false_without_start_time(self):
        self.assertFalse(scan_watchdog_timed_out(None, now=100.0, timeout_s=45))

    def test_scan_watchdog_timeout_returns_false_before_threshold(self):
        self.assertFalse(scan_watchdog_timed_out(100.0, now=144.9, timeout_s=45))

    def test_scan_watchdog_timeout_returns_true_at_threshold(self):
        self.assertTrue(scan_watchdog_timed_out(100.0, now=145.0, timeout_s=45))


if __name__ == "__main__":
    unittest.main()
