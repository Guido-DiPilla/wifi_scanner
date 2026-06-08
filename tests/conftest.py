"""Shared test helpers for service-layer unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from wifi_core.runner import CommandResult


def make_command_result(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> CommandResult:
    """Create a CommandResult instance with defaults for concise tests."""
    return CommandResult(returncode=returncode, stdout=stdout, stderr=stderr)


def make_runner(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> MagicMock:
    """Return a mock CommandRunner whose run() returns a fixed CommandResult."""
    runner = MagicMock()
    runner.run.return_value = make_command_result(
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
    )
    return runner
