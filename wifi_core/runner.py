"""Command runner utilities for system tool execution."""

from __future__ import annotations

from dataclasses import dataclass
import shutil
import subprocess
from typing import Sequence


class CommandRunnerError(RuntimeError):
    """Base command execution error."""


class CommandNotFoundError(CommandRunnerError):
    """Raised when an executable is not available."""


class CommandTimeoutError(CommandRunnerError):
    """Raised when a command exceeds timeout."""


@dataclass
class CommandResult:
    """Normalized command result."""

    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    """Thin wrapper around subprocess for consistent command handling."""

    def command_exists(self, executable: str) -> bool:
        return shutil.which(executable) is not None

    def run(self, argv: Sequence[str], timeout: int) -> CommandResult:
        try:
            proc = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise CommandNotFoundError(f"Command not found: {argv[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise CommandTimeoutError(
                f"Command timed out after {timeout}s: {' '.join(argv)}"
            ) from exc

        return CommandResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
