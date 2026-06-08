"""Unit tests for signal-history retention pruning."""

from __future__ import annotations

from collections import deque
import unittest

from wifi_scanner import prune_signal_history


class WifiScannerHistoryRetentionTests(unittest.TestCase):
    def test_prune_removes_stale_bssids(self):
        history = {
            "AA:AA:AA:AA:AA:01": deque([(10.0, 60)], maxlen=60),
            "AA:AA:AA:AA:AA:02": deque([(11.0, 70)], maxlen=60),
            "AA:AA:AA:AA:AA:03": deque([(12.0, 80)], maxlen=60),
        }

        prune_signal_history(
            history,
            active_bssids={"AA:AA:AA:AA:AA:01", "AA:AA:AA:AA:AA:03"},
            selected_bssid=None,
        )

        self.assertEqual(set(history), {"AA:AA:AA:AA:AA:01", "AA:AA:AA:AA:AA:03"})

    def test_prune_keeps_selected_even_if_not_active(self):
        history = {
            "AA:AA:AA:AA:AA:01": deque([(10.0, 60)], maxlen=60),
            "AA:AA:AA:AA:AA:02": deque([(11.0, 70)], maxlen=60),
        }

        prune_signal_history(
            history,
            active_bssids={"AA:AA:AA:AA:AA:01"},
            selected_bssid="AA:AA:AA:AA:AA:02",
        )

        self.assertEqual(set(history), {"AA:AA:AA:AA:AA:01", "AA:AA:AA:AA:AA:02"})

    def test_prune_caps_total_entries_by_oldest_last_seen(self):
        history = {
            "AA:AA:AA:AA:AA:01": deque([(5.0, 55)], maxlen=60),
            "AA:AA:AA:AA:AA:02": deque([(10.0, 60)], maxlen=60),
            "AA:AA:AA:AA:AA:03": deque([(15.0, 65)], maxlen=60),
            "AA:AA:AA:AA:AA:04": deque([(20.0, 70)], maxlen=60),
        }

        prune_signal_history(
            history,
            active_bssids=set(history),
            selected_bssid="AA:AA:AA:AA:AA:04",
            max_bssids=2,
        )

        self.assertEqual(set(history), {"AA:AA:AA:AA:AA:03", "AA:AA:AA:AA:AA:04"})


if __name__ == "__main__":
    unittest.main()
