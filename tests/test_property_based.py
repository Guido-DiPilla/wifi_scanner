"""Property-based tests for parser and vendor helper invariants."""

from __future__ import annotations

import unittest

from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from wifi_core.adapter_service import (
    _detect_capabilities,
    _detect_supported_bands,
    _detect_supported_standards,
)
from wifi_core.models import WifiNetwork
from wifi_core.nmcli_parser import _to_int, parse_scan_line, split_escaped
from wifi_core.runner import CommandResult
from wifi_core.scanner_service import get_device_dns, get_device_ips
from wifi_core.vendor_lookup import _bssid_to_mac_int, _mac_int_to_oui


def _escape_nmcli_field(value: str) -> str:
    """Escape field separators and backslashes as nmcli-style tokens."""
    return value.replace("\\", r"\\").replace(":", r"\:")


def _mac_to_str(mac_int: int) -> str:
    """Format a 48-bit integer as canonical MAC string."""
    return ":".join(f"{(mac_int >> shift) & 0xFF:02X}" for shift in (40, 32, 24, 16, 8, 0))


class NmcliParserPropertyTests(unittest.TestCase):
    @settings(max_examples=80)
    @given(st.lists(st.text(alphabet=st.characters(blacklist_characters=":\\"), max_size=12), min_size=1, max_size=8))
    def test_split_escaped_plain_tokens_round_trip(self, tokens: list[str]) -> None:
        joined = ":".join(tokens)
        self.assertEqual(split_escaped(joined, ":"), tokens)

    @settings(max_examples=80)
    @given(st.lists(st.text(max_size=8), min_size=1, max_size=6))
    def test_split_escaped_round_trip_with_escaping(self, tokens: list[str]) -> None:
        joined = ":".join(_escape_nmcli_field(token) for token in tokens)
        self.assertEqual(split_escaped(joined, ":"), tokens)

    @settings(max_examples=120)
    @given(st.integers(min_value=-2_000_000, max_value=2_000_000))
    def test_to_int_accepts_valid_integer_strings(self, value: int) -> None:
        self.assertEqual(_to_int(str(value), default=99), value)

    @settings(max_examples=120)
    @given(st.text(min_size=1).filter(lambda s: s.strip("+-").isdigit() is False))
    def test_to_int_returns_default_for_non_numeric(self, raw: str) -> None:
        self.assertEqual(_to_int(raw, default=123), 123)

    @settings(max_examples=100)
    @given(
        ssid=st.text(max_size=16),
        signal=st.integers(min_value=0, max_value=100),
        in_use=st.booleans(),
    )
    def test_parse_scan_line_preserves_core_fields(self, ssid: str, signal: int, in_use: bool) -> None:
        safe_ssid = _escape_nmcli_field(ssid)
        bssid = "AA\\:BB\\:CC\\:DD\\:EE\\:FF"
        line = ":".join(
            [
                "*" if in_use else "",
                safe_ssid,
                bssid,
                "Infra",
                "36",
                "5180 MHz",
                "540 Mbit/s",
                str(signal),
                "****",
                "WPA2",
                "80 MHz",
                "wlan0",
                "",
                "",
            ]
        )

        net = parse_scan_line(line, 1234.0)
        self.assertIsNotNone(net)
        assert net is not None
        self.assertEqual(net.signal, signal)
        self.assertEqual(net.in_use, in_use)
        self.assertEqual(net.bssid, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(net.ssid, ssid if ssid else "<hidden>")

    @settings(max_examples=120)
    @given(st.lists(st.text(max_size=10), min_size=0, max_size=10))
    def test_parse_scan_line_returns_none_when_fields_too_short(self, fields: list[str]) -> None:
        line = ":".join(_escape_nmcli_field(f) for f in fields)
        self.assertIsNone(parse_scan_line(line, 1.0))


class VendorLookupPropertyTests(unittest.TestCase):
    @settings(max_examples=120)
    @given(st.integers(min_value=0, max_value=(1 << 48) - 1))
    def test_bssid_parser_round_trips_mac_int(self, mac_int: int) -> None:
        mac_text = _mac_to_str(mac_int)
        self.assertEqual(_bssid_to_mac_int(mac_text), mac_int)

    @settings(max_examples=120)
    @given(st.integers(min_value=0, max_value=(1 << 48) - 1))
    def test_mac_to_oui_matches_top_24_bits(self, mac_int: int) -> None:
        expected = _mac_to_str(mac_int).split(":")[:3]
        self.assertEqual(_mac_int_to_oui(mac_int).split(":"), expected)


class AdapterServicePropertyTests(unittest.TestCase):
    @settings(max_examples=100)
    @given(
        has24=st.booleans(),
        has5=st.booleans(),
        has6=st.booleans(),
    )
    def test_detect_supported_bands_contains_expected_labels(self, has24: bool, has5: bool, has6: bool) -> None:
        chunks: list[str] = []
        if has24:
            chunks.append("2412")
        if has5:
            chunks.append("5180")
        if has6:
            chunks.append("5955")
        output = " ".join(chunks)

        detected = _detect_supported_bands(output)
        self.assertEqual("2.4 GHz" in detected, has24)
        self.assertEqual("5 GHz" in detected, has5)
        self.assertEqual("6 GHz" in detected, has6)

    @settings(max_examples=100)
    @given(
        ht=st.booleans(),
        vht=st.booleans(),
        he=st.booleans(),
        eht=st.booleans(),
    )
    def test_detect_supported_standards_flags(self, ht: bool, vht: bool, he: bool, eht: bool) -> None:
        chunks: list[str] = []
        if ht:
            chunks.append("HT20")
        if vht:
            chunks.append("VHT80")
        if he:
            chunks.append("HE PHY")
        if eht:
            chunks.append("EHT")
        output = "\n".join(chunks)

        detected = _detect_supported_standards(output)
        self.assertEqual("802.11n (WiFi 4)" in detected, ht)
        self.assertEqual("802.11ac (WiFi 5)" in detected, vht)
        self.assertEqual("802.11ax (WiFi 6)" in detected, he)
        self.assertEqual("802.11be (WiFi 7)" in detected, eht)
        self.assertEqual("802.11a/b/g" in detected, any((ht, vht, he, eht)))

    @settings(max_examples=80)
    @given(output=st.text(max_size=120))
    def test_detect_capabilities_only_returns_known_labels(self, output: str) -> None:
        known = {
            "MU-MIMO",
            "Beamforming",
            "WPA3",
            "OFDMA",
            "160 MHz channels",
            "STBC",
            "LDPC",
            "Dynamic Bandwidth",
        }
        self.assertTrue(set(_detect_capabilities(output)).issubset(known))


class ModelsPropertyTests(unittest.TestCase):
    @settings(max_examples=120)
    @given(
        signal=st.integers(min_value=-200, max_value=300),
        security=st.sampled_from(["WPA3", "WPA2", "WPA", "WEP", "Open", "Other"]),
        congestion=st.integers(min_value=0, max_value=20),
        bandwidth=st.sampled_from(["20 MHz", "40 MHz", "80 MHz", "160 MHz", "bad"]),
    )
    def test_quality_score_clamped_to_zero_hundred(
        self,
        signal: int,
        security: str,
        congestion: int,
        bandwidth: str,
    ) -> None:
        net = WifiNetwork(
            ssid="x",
            bssid="AA:BB:CC:DD:EE:FF",
            mode="Infra",
            channel="1",
            frequency="2412 MHz",
            rate="130 Mbit/s",
            signal=signal,
            bars="**",
            security=security,
            bandwidth=bandwidth,
            congestion=congestion,
        )
        score = net.quality_score
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    @settings(max_examples=120)
    @given(rate_val=st.floats(min_value=0.0, max_value=10_000.0, allow_nan=False, allow_infinity=False))
    def test_theoretical_max_speed_numeric_rate_has_units(self, rate_val: float) -> None:
        net = WifiNetwork(
            ssid="x",
            bssid="AA:BB:CC:DD:EE:FF",
            mode="Infra",
            channel="36",
            frequency="5180 MHz",
            rate=f"{rate_val:.3f} Mbit/s",
            signal=50,
            bars="**",
            security="WPA2",
        )
        speed = net.theoretical_max_speed
        self.assertTrue(speed.endswith("Mbps") or speed.endswith("Gbps"))


class ScannerServicePropertyTests(unittest.TestCase):
    class _FieldRunner:
        def __init__(self, field_outputs: dict[str, str]):
            self._field_outputs = field_outputs

        def run(self, argv: list[str], timeout: int) -> CommandResult:
            field = argv[2]
            return CommandResult(returncode=0, stdout=self._field_outputs.get(field, ""), stderr="")

    @settings(max_examples=100)
    @given(lines=st.lists(st.text(min_size=0, max_size=30), min_size=0, max_size=6))
    def test_get_device_dns_joins_non_empty_non_dash_lines(self, lines: list[str]) -> None:
        stdout = "\n".join(lines)
        runner = self._FieldRunner({"IP4.DNS": stdout, "IP6.DNS": stdout})
        expected_lines = [l.strip() for l in stdout.splitlines() if l.strip() and l.strip() != "--"]
        expected = ", ".join(expected_lines)

        dns4, dns6 = get_device_dns("wlan0", runner=runner)
        self.assertEqual(dns4, expected)
        self.assertEqual(dns6, expected)

    @settings(max_examples=100)
    @given(lines=st.lists(st.text(min_size=0, max_size=30), min_size=0, max_size=6))
    def test_get_device_ips_uses_first_non_empty_non_dash_line(self, lines: list[str]) -> None:
        stdout = "\n".join(lines)
        runner = self._FieldRunner({"IP4.ADDRESS": stdout, "IP6.ADDRESS": stdout})
        filtered = [l.strip() for l in stdout.splitlines() if l.strip() and l.strip() != "--"]
        expected = filtered[0] if filtered else ""

        ipv4, ipv6 = get_device_ips("wlan0", runner=runner)
        self.assertEqual(ipv4, expected)
        self.assertEqual(ipv6, expected)


if __name__ == "__main__":
    unittest.main()
