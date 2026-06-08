"""Unit tests for WifiScannerApp async action orchestration."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from wifi_scanner import WifiScannerApp


class WifiScannerAsyncActionTests(unittest.TestCase):
    def test_run_async_nm_action_starts_worker_and_sets_in_progress_status(self):
        app = WifiScannerApp.__new__(WifiScannerApp)
        app._start_background_task = MagicMock()
        app._show_connection_status = MagicMock()

        app._run_async_nm_action(
            action=lambda: MagicMock(returncode=0, stderr="", stdout=""),
            in_progress_message="Connecting...",
            success_message="Connected",
            failure_prefix="Failed",
            failure_title="Failure",
            exception_status="Error",
            exception_title="Error",
        )

        app._start_background_task.assert_called_once()
        app._show_connection_status.assert_called_once_with("Connecting...", None)


if __name__ == "__main__":
    unittest.main()
