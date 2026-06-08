"""Unit tests for wifi_core.models.WifiNetwork computed properties."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wifi_core.models import WifiNetwork


def _net(**overrides) -> WifiNetwork:
    base = {
        "ssid": "MyNet",
        "bssid": "AA:BB:CC:DD:EE:FF",
        "mode": "Infra",
        "channel": "36",
        "frequency": "5180 MHz",
        "rate": "1200 Mbit/s",
        "signal": 80,
        "bars": "****",
        "security": "WPA2",
        "bandwidth": "80 MHz",
        "device": "wlan0",
        "wpa_flags": "",
        "rsn_flags": "",
        "in_use": False,
        "last_seen": 0.0,
        "congestion": 2,
        "password": "",
    }
    base.update(overrides)
    return WifiNetwork(**base)


class WifiNetworkModelTests(unittest.TestCase):
    def test_band_detection(self):
        self.assertEqual(_net(frequency="2437 MHz").band, "2.4 GHz")
        self.assertEqual(_net(frequency="5180 MHz").band, "5 GHz")
        self.assertEqual(_net(frequency="6.055 GHz").band, "6 GHz")
        self.assertEqual(_net(frequency="unknown").band, "?")
        self.assertEqual(_net(frequency="").band, "?")
        self.assertEqual(_net(frequency="0 MHz").band, "2.4 GHz")

    def test_theoretical_max_speed(self):
        self.assertEqual(_net(rate="600 Mbit/s").theoretical_max_speed, "450 Mbps")
        self.assertEqual(_net(rate="2400 Mbit/s").theoretical_max_speed, "1.8 Gbps")
        self.assertEqual(_net(rate="bad").theoretical_max_speed, "Unknown")

    def test_quality_score_respects_signal_security_congestion_bandwidth(self):
        # Strong, modern, low congestion, wide bandwidth => high score
        best = _net(signal=95, security="WPA3", congestion=1, bandwidth="160 MHz")
        self.assertGreaterEqual(best.quality_score, 95)

        # Weak/open/crowded => low score
        weak = _net(signal=30, security="Open", congestion=8, bandwidth="20 MHz")
        self.assertLessEqual(weak.quality_score, 20)

    def test_quality_score_decreases_as_congestion_increases(self):
        baseline = _net(signal=80, security="WPA2", congestion=0, bandwidth="80 MHz")
        medium = _net(signal=80, security="WPA2", congestion=4, bandwidth="80 MHz")
        high = _net(signal=80, security="WPA2", congestion=7, bandwidth="80 MHz")
        self.assertGreater(baseline.quality_score, medium.quality_score)
        self.assertGreater(medium.quality_score, high.quality_score)

    def test_encryption_type_mapping(self):
        self.assertEqual(_net(security="WPA3", rsn_flags="").encryption_type, "WPA3 (Modern)")
        self.assertEqual(_net(security="WPA2", rsn_flags="").encryption_type, "WPA2 (Secure)")
        self.assertEqual(_net(security="WPA", rsn_flags="").encryption_type, "WPA (Legacy)")
        self.assertEqual(_net(security="WEP", rsn_flags="").encryption_type, "WEP (Insecure)")
        self.assertEqual(_net(security="Open", rsn_flags="").encryption_type, "Open (No encryption)")

    def test_last_seen_str(self):
        self.assertEqual(_net(last_seen=0).last_seen_str, "Just now")
        with patch("wifi_core.models.time.time", return_value=100.0):
            self.assertEqual(_net(last_seen=80.0).last_seen_str, "20s ago")
            self.assertEqual(_net(last_seen=10.0).last_seen_str, "1m ago")
            self.assertEqual(_net(last_seen=-7100.0).last_seen_str, "2h ago")

    def test_signal_dbm(self):
        self.assertEqual(_net(signal=100).signal_dbm, "-50 dBm")
        self.assertEqual(_net(signal=0).signal_dbm, "-100 dBm")

    def test_quality_label_all_tiers(self):
        self.assertEqual(_net(signal=80).quality_label, "Excellent")
        self.assertEqual(_net(signal=60).quality_label, "Good")
        self.assertEqual(_net(signal=40).quality_label, "Fair")
        self.assertEqual(_net(signal=20).quality_label, "Weak")

    def test_quality_color_all_tiers(self):
        self.assertEqual(_net(signal=80).quality_color, "#00e676")
        self.assertEqual(_net(signal=60).quality_color, "#69f0ae")
        self.assertEqual(_net(signal=40).quality_color, "#ffca28")
        self.assertEqual(_net(signal=20).quality_color, "#ef5350")

    def test_bandwidth_mhz_unparseable_returns_default(self):
        self.assertEqual(_net(bandwidth="bad").bandwidth_mhz, 20)

    def test_vendor_property_delegates_to_get_vendor(self):
        with patch("wifi_core.models.get_vendor", return_value="TP-Link"):
            net = _net(bssid="00:11:22:33:44:55")
            self.assertEqual(net.vendor, "TP-Link")

    def test_quality_score_low_congestion_penalty(self):
        # congestion=2 > CONGESTION_THRESHOLD_LOW (1) hits the low-penalty branch
        with_low = _net(signal=80, security="WPA2", congestion=2, bandwidth="80 MHz")
        no_congestion = _net(signal=80, security="WPA2", congestion=0, bandwidth="80 MHz")
        self.assertLess(with_low.quality_score, no_congestion.quality_score)

    def test_quality_score_40mhz_bandwidth_bonus(self):
        # bandwidth_mhz=40 hits BANDWIDTH_BONUS_40 branch
        forty = _net(signal=70, security="WPA2", congestion=0, bandwidth="40 MHz")
        twenty = _net(signal=70, security="WPA2", congestion=0, bandwidth="20 MHz")
        self.assertGreater(forty.quality_score, twenty.quality_score)


if __name__ == "__main__":
    unittest.main()
