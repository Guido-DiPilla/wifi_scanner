import unittest

from wifi_core.nmcli_parser import _to_int, parse_scan_line, split_escaped


class NmcliParserTests(unittest.TestCase):
    def test_split_escaped_uses_colon_default_separator(self):
        parts = split_escaped("left:right")
        self.assertEqual(parts, ["left", "right"])

    def test_split_escaped_handles_escaped_colon(self):
        parts = split_escaped(r"a\:b:c")
        self.assertEqual(parts, ["a:b", "c"])

    def test_parse_scan_line_with_hidden_ssid(self):
        line = r":\:hidden:AA\:BB\:CC\:DD\:EE\:FF:Infra:36:5180 MHz:540 Mbit/s:80:****:WPA2:80 MHz:wlan0:::"
        net = parse_scan_line(line, 1000.0)
        self.assertIsNotNone(net)
        assert net is not None
        self.assertEqual(net.ssid, ":hidden")
        self.assertEqual(net.bssid, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(net.channel, "36")
        self.assertEqual(net.signal, 80)

    def test_parse_scan_line_empty_ssid_maps_hidden(self):
        line = r"::AA\:BB\:CC\:DD\:EE\:11:Infra:1:2412 MHz:130 Mbit/s:55:****:WPA2:20 MHz:wlan0:::"
        net = parse_scan_line(line, 1000.0)
        self.assertIsNotNone(net)
        assert net is not None
        self.assertEqual(net.ssid, "<hidden>")
        self.assertEqual(net.security, "WPA2")

    def test_split_escaped_trailing_backslash_preserved(self):
        # A trailing backslash (escaped=True at end of string) must be kept
        parts = split_escaped("abc\\")
        self.assertEqual(parts, ["abc\\"])

    def test_to_int_non_numeric_returns_default(self):
        self.assertEqual(_to_int("abc"), 0)
        self.assertEqual(_to_int("abc", 99), 99)

    def test_to_int_non_numeric_default_argument_is_zero(self):
        # This locks in the implicit default behavior (without passing default).
        self.assertEqual(_to_int("not-a-number"), 0)

    def test_parse_scan_line_too_few_fields_returns_none(self):
        self.assertIsNone(parse_scan_line("a:b:c", 1000.0))

    def test_parse_scan_line_minimum_supported_arity(self):
        # Exactly 11 fields should still parse (device/wpa/rsn can be absent).
        line = (
            r"*:StarNet:AA\:BB\:CC\:DD\:EE\:22:Infra:11:2462 MHz:300 Mbit/s:70:****:WPA2:40 MHz"
        )
        net = parse_scan_line(line, 1000.0)
        self.assertIsNotNone(net)
        assert net is not None
        self.assertEqual(net.ssid, "StarNet")
        self.assertEqual(net.device, "")
        self.assertEqual(net.wpa_flags, "")
        self.assertEqual(net.rsn_flags, "")

    def test_parse_scan_line_in_use_is_true_for_star_prefix(self):
        line = (
            r"*:Connected:AA\:BB\:CC\:DD\:EE\:33:Infra:36:5180 MHz:540 Mbit/s:81:****:WPA2:80 MHz:wlan0:::"
        )
        net = parse_scan_line(line, 1000.0)
        self.assertIsNotNone(net)
        assert net is not None
        self.assertIs(net.in_use, True)

    def test_parse_scan_line_in_use_is_false_without_star(self):
        line = (
            r":Guest:AA\:BB\:CC\:DD\:EE\:44:Infra:1:2412 MHz:130 Mbit/s:40:**:Open:20 MHz:wlan0:::"
        )
        net = parse_scan_line(line, 1000.0)
        self.assertIsNotNone(net)
        assert net is not None
        self.assertIs(net.in_use, False)

    def test_parse_scan_line_maps_all_primary_and_optional_fields(self):
        ts = 1234.5
        line = (
            r"*:Office:AA\:BB\:CC\:DD\:EE\:55:Infra:149:5745 MHz:866 Mbit/s:67:***:WPA2 WPA3:80 MHz:wlan1:sae:pair_ccmp"
        )
        net = parse_scan_line(line, ts)
        self.assertIsNotNone(net)
        assert net is not None

        self.assertEqual(net.ssid, "Office")
        self.assertEqual(net.bssid, "AA:BB:CC:DD:EE:55")
        self.assertEqual(net.mode, "Infra")
        self.assertEqual(net.channel, "149")
        self.assertEqual(net.frequency, "5745 MHz")
        self.assertEqual(net.rate, "866 Mbit/s")
        self.assertEqual(net.signal, 67)
        self.assertEqual(net.bars, "***")
        self.assertEqual(net.security, "WPA2 WPA3")
        self.assertEqual(net.bandwidth, "80 MHz")
        self.assertEqual(net.device, "wlan1")
        self.assertEqual(net.wpa_flags, "sae")
        self.assertEqual(net.rsn_flags, "pair_ccmp")
        self.assertTrue(net.in_use)
        self.assertEqual(net.last_seen, ts)
        self.assertEqual(net.password, "")

    def test_parse_scan_line_defaults_open_and_20mhz_when_empty(self):
        line = (
            r":Cafe:AA\:BB\:CC\:DD\:EE\:66:Infra:6:2437 MHz:130 Mbit/s:55:***:::wlan0:::"
        )
        net = parse_scan_line(line, 42.0)
        self.assertIsNotNone(net)
        assert net is not None
        self.assertEqual(net.security, "Open")
        self.assertEqual(net.bandwidth, "20 MHz")


if __name__ == "__main__":
    unittest.main()
