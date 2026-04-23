"""Smoke tests that ensure key UI modules import cleanly.

This supports coverage accounting and catches import-time regressions.
"""

from __future__ import annotations

import importlib
import unittest


class ImportSmokeTests(unittest.TestCase):
    def test_import_scanner_module(self):
        module = importlib.import_module("wifi_scanner")
        self.assertIsNotNone(module)

    def test_import_ui_widgets_module(self):
        module = importlib.import_module("ui_widgets")
        self.assertIsNotNone(module)

    def test_import_ui_dialogs_module(self):
        module = importlib.import_module("ui_dialogs")
        self.assertIsNotNone(module)


if __name__ == "__main__":
    unittest.main()
