import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from wifi_core import vendor_lookup
from wifi_core.vendor_lookup import PrefixEntry


class VendorLookupTests(unittest.TestCase):
    def test_normalize_oui_variants(self):
        self.assertEqual(vendor_lookup._normalize_oui("aa-bb-cc"), "AA:BB:CC")
        self.assertEqual(vendor_lookup._normalize_oui("aabbcc"), "AA:BB:CC")
        self.assertEqual(vendor_lookup._normalize_oui("AA:BB:CC"), "AA:BB:CC")
        self.assertIsNone(vendor_lookup._normalize_oui("not-an-oui"))

    def test_parse_prefix_token_validation_paths(self):
        self.assertIsNone(vendor_lookup._parse_prefix_token(""))
        self.assertIsNone(vendor_lookup._parse_prefix_token("11:22:33/notint"))
        self.assertIsNone(vendor_lookup._parse_prefix_token("11:22:33/0"))
        self.assertIsNone(vendor_lookup._parse_prefix_token("11:22:33/60"))
        self.assertIsNone(vendor_lookup._parse_prefix_token("11:22:33/28"))  # exceeds available bits
        self.assertIsNotNone(vendor_lookup._parse_prefix_token("11:22:33/24"))

    def test_parse_ieee_base16_range_invalid_inputs(self):
        oui24 = 0xAABBCC
        self.assertIsNone(vendor_lookup._parse_ieee_base16_range("F2F000", oui24))
        self.assertIsNone(vendor_lookup._parse_ieee_base16_range("F2F000-F2FFFF", None))
        self.assertIsNone(vendor_lookup._parse_ieee_base16_range("F2F00-F2FFFF", oui24))
        self.assertIsNone(vendor_lookup._parse_ieee_base16_range("GGG000-FFFFFF", oui24))
        self.assertIsNone(vendor_lookup._parse_ieee_base16_range("F2FFFF-F2F000", oui24))

    def test_refresh_authoritative_ieee_cache_returns_false_when_cache_exists_and_not_forced(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            remote_sources = (
                ("oui.txt", "https://example.com/oui.txt"),
                ("oui36.txt", "https://example.com/oui36.txt"),
            )
            for name, _ in remote_sources:
                (cache_dir / name).write_text("already-cached", encoding="utf-8")

            with patch.object(vendor_lookup, "_CACHE_DIR", cache_dir), \
                 patch.object(vendor_lookup, "_IEEE_REMOTE_SOURCES", remote_sources), \
                 patch("wifi_core.vendor_lookup.urllib.request.urlopen") as mock_urlopen:
                refreshed = vendor_lookup.refresh_authoritative_ieee_cache(force=False)

        self.assertFalse(refreshed)
        mock_urlopen.assert_not_called()

    def test_refresh_authoritative_ieee_cache_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            remote_sources = (("oui.txt", "https://example.com/oui.txt"),)

            response = MagicMock()
            response.read.return_value = b"AA-BB-CC   (hex)\tVendor One\n"
            response.__enter__.return_value = response
            response.__exit__.return_value = False

            with patch.object(vendor_lookup, "_CACHE_DIR", cache_dir), \
                 patch.object(vendor_lookup, "_IEEE_REMOTE_SOURCES", remote_sources), \
                 patch("wifi_core.vendor_lookup.urllib.request.urlopen", return_value=response):
                refreshed = vendor_lookup.refresh_authoritative_ieee_cache(force=True)

            cached_file = cache_dir / "oui.txt"
            self.assertTrue(refreshed)
            self.assertTrue(cached_file.exists())
            self.assertIn("(hex)", cached_file.read_text(encoding="utf-8"))

    def test_refresh_authoritative_ieee_cache_failure_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            remote_sources = (("oui.txt", "https://example.com/oui.txt"),)

            with patch.object(vendor_lookup, "_CACHE_DIR", cache_dir), \
                 patch.object(vendor_lookup, "_IEEE_REMOTE_SOURCES", remote_sources), \
                 patch(
                     "wifi_core.vendor_lookup.urllib.request.urlopen",
                     side_effect=OSError("network down"),
                 ):
                self.assertFalse(vendor_lookup.refresh_authoritative_ieee_cache(force=True))

            bad_response = MagicMock()
            bad_response.read.return_value = b"this content is not an IEEE OUI file"
            bad_response.__enter__.return_value = bad_response
            bad_response.__exit__.return_value = False
            with patch.object(vendor_lookup, "_CACHE_DIR", cache_dir), \
                 patch.object(vendor_lookup, "_IEEE_REMOTE_SOURCES", remote_sources), \
                 patch("wifi_core.vendor_lookup.urllib.request.urlopen", return_value=bad_response):
                self.assertFalse(vendor_lookup.refresh_authoritative_ieee_cache(force=True))

    def test_reload_vendor_database_force_refresh_and_helpers(self):
        with patch.object(vendor_lookup, "refresh_authoritative_ieee_cache") as refresh_mock, \
             patch.object(vendor_lookup, "_reload_vendor_state") as reload_mock, \
             patch.object(vendor_lookup, "_OUI_DB", {"AA:BB:CC": "Vendor"}), \
             patch.object(vendor_lookup, "_OUI_PREFIX_DB", []), \
             patch.object(vendor_lookup, "_OUI_DB_PATH", Path("/tmp/manuf")):
            loaded = vendor_lookup.reload_vendor_database(force_refresh=True)
            self.assertTrue(loaded)
            self.assertTrue(vendor_lookup.is_system_manuf_loaded())
            self.assertEqual(vendor_lookup.system_manuf_path(), "/tmp/manuf")

        refresh_mock.assert_called_once_with(force=True)
        reload_mock.assert_called_once_with()

    def test_load_wireshark_manuf_from_system_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manuf_path = Path(tmpdir) / "manuf"
            manuf_path.write_text(
                "# comment\n"
                "AA:BB:CC\tMyVendor\n"
                "11:22:33/24\tOtherVendor\n"
                "11:22:80/20\tMask20Vendor\n"
                "11:22:33:80/28\tMask28Vendor\n",
                encoding="utf-8",
            )

            with patch.object(vendor_lookup, "_MANUF_PATHS", (manuf_path,)):
                db, prefix_db, selected_path = vendor_lookup._load_wireshark_manuf()

        self.assertEqual(selected_path, manuf_path)
        self.assertEqual(db.get("AA:BB:CC"), "MyVendor")
        self.assertEqual(db.get("11:22:33"), "OtherVendor")
        self.assertTrue(any(vendor == "Mask20Vendor" for _m, _v, vendor, bits in prefix_db if bits == 20))
        self.assertTrue(any(vendor == "Mask28Vendor" for _m, _v, vendor, bits in prefix_db if bits == 28))

    def test_load_wireshark_manuf_returns_empty_when_missing(self):
        with patch.object(vendor_lookup, "_MANUF_PATHS", (Path("/definitely/missing/manuf"),)):
            db, prefix_db, selected_path = vendor_lookup._load_wireshark_manuf()

        self.assertEqual(db, {})
        self.assertEqual(prefix_db, [])
        self.assertIsNone(selected_path)

    def test_load_ieee_oui_from_system_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            oui_path = Path(tmpdir) / "oui.txt"
            oui_path.write_text(
                "AA-BB-CC   (hex)\tVendor One\n"
                "112233     (base 16)\tVendor Two\n"
                "invalid line\n",
                encoding="utf-8",
            )

            with patch.object(vendor_lookup, "_SYSTEM_IEEE_OUI_PATHS", (oui_path,)):
                with patch.object(vendor_lookup, "_CACHE_DIR", Path("/definitely/missing/cache")):
                    db, selected_path = vendor_lookup._load_ieee_oui()

        self.assertEqual(selected_path, oui_path)
        self.assertEqual(db.get("AA:BB:CC"), "Vendor One")
        self.assertEqual(db.get("11:22:33"), "Vendor Two")

    def test_load_system_oui_db_falls_back_to_ieee_when_manuf_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            oui_path = Path(tmpdir) / "oui.txt"
            oui_path.write_text("AA-BB-CC   (hex)\tVendor One\n", encoding="utf-8")

            with patch.object(vendor_lookup, "_MANUF_PATHS", (Path("/definitely/missing/manuf"),)):
                with patch.object(vendor_lookup, "_SYSTEM_IEEE_OUI_PATHS", (oui_path,)):
                    with patch.object(vendor_lookup, "_CACHE_DIR", Path("/definitely/missing/cache")):
                        db, prefix_db, selected_path = vendor_lookup._load_system_oui_db()

        self.assertEqual(selected_path, oui_path)
        self.assertEqual(db.get("AA:BB:CC"), "Vendor One")
        self.assertTrue(any(vendor == "Vendor One" for _m, _v, vendor, bits in prefix_db if bits == 24))

    def test_get_vendor_uses_loaded_oui_prefix(self):
        with patch.object(vendor_lookup, "_OUI_DB", {"AA:BB:CC": "TestVendor"}), \
             patch.object(vendor_lookup, "_OUI_PREFIX_DB", []):
            self.assertEqual(vendor_lookup.get_vendor("aa:bb:cc:dd:ee:ff"), "TestVendor")
            self.assertEqual(vendor_lookup.get_vendor("ff:ee:dd:cc:bb:aa"), "Unknown")

    def test_get_vendor_uses_longest_prefix_match(self):
        with patch.object(vendor_lookup, "_OUI_DB", {}), \
             patch.object(
                 vendor_lookup,
                 "_OUI_PREFIX_DB",
                 [
                     # Sorted DESC by prefix_bits (most specific first) to match real behavior
                     PrefixEntry(mask=0xFFFFFFFFF000, value=0xF8731A8D8000, vendor="Vendor36", prefix_bits=36),
                     PrefixEntry(mask=0xFFFFFFF00000, value=0xF8731A800000, vendor="Vendor28", prefix_bits=28),
                     PrefixEntry(mask=0xFFFFFF000000, value=0xF8731A000000, vendor="Vendor24", prefix_bits=24),
                 ],
             ):
            self.assertEqual(vendor_lookup.get_vendor("F8:73:1A:8D:81:40"), "Vendor36")
            self.assertEqual(vendor_lookup.get_vendor("F8:73:1A:8A:22:11"), "Vendor28")
            self.assertEqual(vendor_lookup.get_vendor("F8:73:1A:00:22:11"), "Vendor24")

    def test_get_vendor_returns_unknown_for_malformed_bssid(self):
        with patch.object(vendor_lookup, "_OUI_DB", {"AA:BB:CC": "VendorX"}), \
             patch.object(vendor_lookup, "_OUI_PREFIX_DB", []):
            self.assertEqual(vendor_lookup.get_vendor("invalid"), "Unknown")
            self.assertEqual(vendor_lookup.get_vendor("AA:BB:CC"), "Unknown")
            self.assertEqual(vendor_lookup.get_vendor(""), "Unknown")

    def test_parse_ieee_base16_range_with_current_oui24(self):
        oui24 = 0xAABBCC
        parsed = vendor_lookup._parse_ieee_base16_range("F2F000-F2FFFF", oui24)
        self.assertIsNotNone(parsed)
        value, _mask, prefix_bits = parsed
        self.assertGreaterEqual(prefix_bits, 24)
        self.assertEqual((value >> 24) & 0xFFFFFF, oui24)


if __name__ == "__main__":
    unittest.main()
