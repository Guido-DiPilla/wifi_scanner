"""Data models for Wi-Fi scanner domain."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import time

from wifi_core.vendor_lookup import get_vendor
from config import (
    BANDWIDTH_BONUS_160,
    BANDWIDTH_BONUS_40,
    BANDWIDTH_BONUS_80,
    CONGESTION_PENALTY_HIGH,
    CONGESTION_PENALTY_LOW,
    CONGESTION_PENALTY_MED,
    CONGESTION_THRESHOLD_HIGH,
    CONGESTION_THRESHOLD_LOW,
    CONGESTION_THRESHOLD_MED,
    OPEN_PENALTY,
    SIGNAL_WEIGHT,
    THROUGHPUT_EFFICIENCY,
    WPA2_BONUS,
    WPA3_BONUS,
)


@dataclass
class WifiNetwork:
    """Normalized representation of one scanned Wi-Fi network."""

    ssid: str
    bssid: str
    mode: str
    channel: str
    frequency: str
    rate: str
    signal: int
    bars: str
    security: str
    bandwidth: str = ""
    device: str = ""
    wpa_flags: str = ""
    rsn_flags: str = ""
    in_use: bool = False
    last_seen: float = 0.0
    congestion: int = 0
    password: str = ""

    @cached_property
    def vendor(self) -> str:
        """Return vendor/manufacturer name resolved from BSSID prefix."""
        return get_vendor(self.bssid)

    @property
    def signal_dbm(self) -> str:
        """Estimate RSSI in dBm from nmcli percentage signal value."""
        dbm = -100 + (self.signal / 2)
        return f"{dbm:.0f} dBm"

    @property
    def band(self) -> str:
        """Return frequency band label derived from network frequency."""
        try:
            if "GHz" in self.frequency:
                freq_mhz = float(self.frequency.replace(" GHz", "").strip()) * 1000
            else:
                freq_mhz = float(self.frequency.replace(" MHz", "").strip())
        except (ValueError, AttributeError):
            return "?"
        if freq_mhz < 3000:
            return "2.4 GHz"
        if freq_mhz < 6000:
            return "5 GHz"
        return "6 GHz"

    @property
    def quality_label(self) -> str:
        """Return a human-friendly quality tier from signal percentage."""
        if self.signal >= 80:
            return "Excellent"
        if self.signal >= 60:
            return "Good"
        if self.signal >= 40:
            return "Fair"
        return "Weak"

    @property
    def quality_color(self) -> str:
        """Return UI color associated with current signal quality tier."""
        if self.signal >= 80:
            return "#00e676"
        if self.signal >= 60:
            return "#69f0ae"
        if self.signal >= 40:
            return "#ffca28"
        return "#ef5350"

    @property
    def bandwidth_mhz(self) -> int:
        """Return parsed channel width in MHz, defaulting to 20."""
        try:
            return int(self.bandwidth.split()[0]) if self.bandwidth else 20
        except (ValueError, IndexError):
            return 20

    @property
    def theoretical_max_speed(self) -> str:
        """Estimate practical throughput from link rate and efficiency factor."""
        try:
            rate_val = float(self.rate.split()[0]) if self.rate else 0.0
        except (ValueError, IndexError):
            return "Unknown"
        max_speed = rate_val * THROUGHPUT_EFFICIENCY
        if max_speed >= 1000:
            return f"{max_speed / 1000:.1f} Gbps"
        return f"{max_speed:.0f} Mbps"

    @property
    def quality_score(self) -> int:
        """Compute a weighted 0-100 score using signal, security, and congestion."""
        score = self.signal * SIGNAL_WEIGHT
        if "WPA3" in self.security:
            score += WPA3_BONUS
        elif "WPA2" in self.security:
            score += WPA2_BONUS
        elif self.security == "Open":
            score -= OPEN_PENALTY

        if self.congestion > CONGESTION_THRESHOLD_HIGH:
            score -= CONGESTION_PENALTY_HIGH
        elif self.congestion > CONGESTION_THRESHOLD_MED:
            score -= CONGESTION_PENALTY_MED
        elif self.congestion > CONGESTION_THRESHOLD_LOW:
            score -= CONGESTION_PENALTY_LOW

        if self.bandwidth_mhz >= 160:
            score += BANDWIDTH_BONUS_160
        elif self.bandwidth_mhz >= 80:
            score += BANDWIDTH_BONUS_80
        elif self.bandwidth_mhz >= 40:
            score += BANDWIDTH_BONUS_40

        return max(0, min(100, int(score)))

    @property
    def encryption_type(self) -> str:
        """Return normalized encryption classification for display."""
        if "WPA3" in self.rsn_flags or "WPA3" in self.security:
            return "WPA3 (Modern)"
        if "WPA2" in self.security or "802.1X" in self.rsn_flags:
            return "WPA2 (Secure)"
        if "WPA" in self.security:
            return "WPA (Legacy)"
        if "WEP" in self.security:
            return "WEP (Insecure)"
        return "Open (No encryption)"

    @property
    def last_seen_str(self) -> str:
        """Return relative time since this network was last observed."""
        if self.last_seen == 0:
            return "Just now"
        elapsed = time.time() - self.last_seen
        if elapsed < 60:
            return f"{int(elapsed)}s ago"
        if elapsed < 3600:
            return f"{int(elapsed/60)}m ago"
        return f"{int(elapsed/3600)}h ago"
