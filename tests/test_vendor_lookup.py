import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wifi_core import vendor_lookup
from wifi_core.vendor_lookup import PrefixEntry


class VendorLookupTests(unittest.TestCase):
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
