"""
tests/test_runner.py — Unit tests for wifi_core.runner.CommandRunner.

All subprocess calls are mocked so these tests run without any system tools.
"""
from __future__ import annotations

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from wifi_core.runner import (
    CommandNotFoundError,
    CommandResult,
    CommandRunner,
    CommandTimeoutError,
)


class TestCommandExists(unittest.TestCase):
    def setUp(self):
        self.runner = CommandRunner()

    def test_returns_true_when_tool_found(self):
        with patch("shutil.which", return_value="/usr/bin/nmcli"):
            self.assertTrue(self.runner.command_exists("nmcli"))

    def test_returns_false_when_tool_missing(self):
        with patch("shutil.which", return_value=None):
            self.assertFalse(self.runner.command_exists("no_such_tool"))


class TestRun(unittest.TestCase):
    def setUp(self):
        self.runner = CommandRunner()

    def _mock_completed(self, stdout="", stderr="", returncode=0):
        proc = MagicMock(spec=subprocess.CompletedProcess)
        proc.stdout = stdout
        proc.stderr = stderr
        proc.returncode = returncode
        return proc

    def test_successful_run_returns_result(self):
        proc = self._mock_completed(stdout="hello", returncode=0)
        with patch("subprocess.run", return_value=proc):
            result = self.runner.run(["echo", "hello"], timeout=5)
        self.assertIsInstance(result, CommandResult)
        self.assertEqual(result.stdout, "hello")
        self.assertEqual(result.returncode, 0)

    def test_non_zero_returncode_still_returns_result(self):
        proc = self._mock_completed(stderr="oops", returncode=1)
        with patch("subprocess.run", return_value=proc):
            result = self.runner.run(["false"], timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "oops")

    def test_file_not_found_raises_command_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaises(CommandNotFoundError):
                self.runner.run(["no_such_cmd"], timeout=5)

    def test_timeout_raises_command_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("x", 1)):
            with self.assertRaises(CommandTimeoutError):
                self.runner.run(["sleep", "999"], timeout=1)


if __name__ == "__main__":
    unittest.main()
