"""Unit tests for wifi_core.adapter_service parsing helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wifi_core.adapter_service import (
    _detect_capabilities,
    _detect_supported_bands,
    _detect_supported_standards,
    get_wifi_adapter_info,
)
from wifi_core.runner import CommandResult


class AdapterServiceParsingTests(unittest.TestCase):
    def test_detect_supported_bands(self):
        output = "2412 MHz\n5180 MHz\n5955 MHz\n"
        self.assertEqual(_detect_supported_bands(output), ["2.4 GHz", "5 GHz", "6 GHz"])

    def test_detect_supported_bands_empty(self):
        self.assertEqual(_detect_supported_bands(""), [])

    def test_detect_supported_standards(self):
        output = "HT20\nVHT80\nHE PHY\nEHT\n"
        standards = _detect_supported_standards(output)
        self.assertIn("802.11n (WiFi 4)", standards)
        self.assertIn("802.11ac (WiFi 5)", standards)
        self.assertIn("802.11ax (WiFi 6)", standards)
        self.assertIn("802.11be (WiFi 7)", standards)
        self.assertIn("802.11a/b/g", standards)

    def test_detect_supported_standards_empty(self):
        self.assertEqual(_detect_supported_standards(""), [])

    def test_detect_capabilities(self):
        output = "MU-MIMO\nSU Beamformee\nSAE\nHE PHY\nVHT160\nSTBC\nLDPC\nDynamic channel bandwidth\n"
        caps = _detect_capabilities(output)
        self.assertIn("MU-MIMO", caps)
        self.assertIn("Beamforming", caps)
        self.assertIn("WPA3", caps)
        self.assertIn("OFDMA", caps)
        self.assertIn("160 MHz channels", caps)
        self.assertIn("STBC", caps)
        self.assertIn("LDPC", caps)
        self.assertIn("Dynamic Bandwidth", caps)


class GetWifiAdapterInfoTests(unittest.TestCase):
    """Outcome-based tests for get_wifi_adapter_info() using a stub CommandRunner."""

    @staticmethod
    def _make_runner(available_tools, run_table):
        """Return a stub CommandRunner with canned responses.

        available_tools: iterable of tool names that report as installed
        run_table: dict mapping " ".join(argv) -> stdout string
        """
        available = set(available_tools)

        class _Stub:
            def command_exists(self, executable):
                return executable in available

            def run(self, argv, timeout):
                key = " ".join(argv)
                return CommandResult(returncode=0, stdout=run_table.get(key, ""), stderr="")

        return _Stub()

    def test_no_wifi_device_returns_empty_info(self):
        runner = self._make_runner(
            available_tools=[],
            run_table={"nmcli -t -f DEVICE,TYPE device": "eth0:ethernet\n"},
        )
        with patch("builtins.open", side_effect=FileNotFoundError):
            info = get_wifi_adapter_info(runner)
        self.assertEqual(info["device"], "")
        self.assertEqual(info["supported_bands"], [])
        self.assertEqual(info["missing_tools"], [])

    def test_iw_missing_returns_early_with_placeholder_values(self):
        runner = self._make_runner(
            available_tools=["ethtool"],
            run_table={
                "nmcli -t -f DEVICE,TYPE device": "wlan0:wifi\n",
                "ethtool -i wlan0": "driver: iwlwifi\nversion: 5.15\nfirmware-version: 72.abc.0\n",
            },
        )
        with patch("builtins.open", side_effect=FileNotFoundError):
            info = get_wifi_adapter_info(runner)
        self.assertEqual(info["device"], "wlan0")
        self.assertIn("iw", info["missing_tools"])
        self.assertEqual(info["tx_power"], "Install 'iw' tool")
        self.assertEqual(info["regulatory_domain"], "Install 'iw' tool")
        # Bands/standards are not populated when iw is absent
        self.assertEqual(info["supported_bands"], [])
        self.assertEqual(info["supported_standards"], [])

    def test_ethtool_missing_added_to_missing_tools(self):
        runner = self._make_runner(
            available_tools=["iw"],
            run_table={
                "nmcli -t -f DEVICE,TYPE device": "wlan0:wifi\n",
                "iw dev wlan0 info": "    type managed\n    wiphy 0\n    txpower 20.00 dBm\n",
                "iw reg get": "country DE: DFS-ETSI\n",
                "iw phy phy0 info": "2412 MHz\n5180 MHz\nHT20\nVHT80\n",
            },
        )
        with patch("builtins.open", side_effect=FileNotFoundError):
            info = get_wifi_adapter_info(runner)
        self.assertIn("ethtool", info["missing_tools"])
        self.assertNotIn("iw", info["missing_tools"])
        self.assertEqual(info["device"], "wlan0")

    def test_happy_path_populates_all_fields(self):
        runner = self._make_runner(
            available_tools=["iw", "ethtool"],
            run_table={
                "nmcli -t -f DEVICE,TYPE device": "wlan0:wifi\n",
                "ethtool -i wlan0": "driver: iwlwifi\nversion: 5.15\nfirmware-version: 72.abc.0\n",
                "iw dev wlan0 info": "    type managed\n    wiphy 0\n    txpower 22.00 dBm\n",
                "iw reg get": "country US: DFS-FCC\n",
                "iw phy phy0 info": "2412 MHz\n5180 MHz\nHT20\nVHT80\nHE PHY\n",
            },
        )
        with patch("builtins.open", side_effect=FileNotFoundError):
            info = get_wifi_adapter_info(runner)
        self.assertEqual(info["device"], "wlan0")
        self.assertEqual(info["driver"], "iwlwifi")
        self.assertEqual(info["driver_version"], "5.15")
        self.assertEqual(info["firmware_version"], "72.abc.0")
        self.assertEqual(info["interface_mode"], "managed")
        self.assertEqual(info["tx_power"], "22.00 dBm")
        self.assertEqual(info["regulatory_domain"], "US")
        self.assertIn("2.4 GHz", info["supported_bands"])
        self.assertIn("5 GHz", info["supported_bands"])
        self.assertIn("802.11n (WiFi 4)", info["supported_standards"])
        self.assertIn("802.11ac (WiFi 5)", info["supported_standards"])
        self.assertIn("802.11ax (WiFi 6)", info["supported_standards"])
        self.assertEqual(info["missing_tools"], [])

    def test_global_regulatory_domain(self):
        runner = self._make_runner(
            available_tools=["iw"],
            run_table={
                "nmcli -t -f DEVICE,TYPE device": "wlan0:wifi\n",
                "iw dev wlan0 info": "    type managed\n    wiphy 0\n    txpower 20.00 dBm\n",
                "iw reg get": "global\n",
                "iw phy phy0 info": "",
            },
        )
        with patch("builtins.open", side_effect=FileNotFoundError):
            info = get_wifi_adapter_info(runner)
        self.assertEqual(info["regulatory_domain"], "Global (00)")


if __name__ == "__main__":
    unittest.main()
