import unittest

from wifi_core.nmcli_parser import _to_int, parse_scan_line, split_escaped


class NmcliParserTests(unittest.TestCase):
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

    def test_parse_scan_line_too_few_fields_returns_none(self):
        self.assertIsNone(parse_scan_line("a:b:c", 1000.0))


if __name__ == "__main__":
    unittest.main()
