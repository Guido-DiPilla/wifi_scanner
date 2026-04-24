"""NetworkManager connection operations."""

from __future__ import annotations

from wifi_core.runner import CommandNotFoundError, CommandResult, CommandRunner, CommandTimeoutError


_DEFAULT_RUNNER = CommandRunner()


def _run_nmcli(
    argv: list[str],
    timeout: int,
    timeout_message: str,
    runner: CommandRunner,
) -> CommandResult:
    """Run an nmcli command and normalize common execution errors."""
    try:
        return runner.run(argv, timeout=timeout)
    except CommandNotFoundError as exc:
        raise RuntimeError("nmcli not found. Please install NetworkManager") from exc
    except CommandTimeoutError as exc:
        raise RuntimeError(timeout_message) from exc


def connect_using_profile(ssid: str, runner: CommandRunner | None = None) -> CommandResult:
    """Activate an existing NetworkManager connection profile by SSID name."""
    active_runner = runner or _DEFAULT_RUNNER
    return _run_nmcli(
        ["nmcli", "connection", "up", ssid],
        timeout=30,
        timeout_message=f"Activating connection profile '{ssid}' timed out after 30 seconds.",
        runner=active_runner,
    )


def connect_to_network(
    ssid: str,
    bssid: str | None,
    password: str | None,
    runner: CommandRunner | None = None,
) -> CommandResult:
    """Connect to a network directly, optionally targeting BSSID and password."""
    active_runner = runner or _DEFAULT_RUNNER
    cmd = ["nmcli", "device", "wifi", "connect", bssid if bssid else ssid]
    if password:
        cmd.extend(["password", password])

    return _run_nmcli(
        cmd,
        timeout=30,
        timeout_message=(
            f"Connection to {ssid} timed out after 30 seconds. "
            "The network may be out of range or not responding."
        ),
        runner=active_runner,
    )


def disconnect_current_device(runner: CommandRunner | None = None) -> CommandResult:
    """Disconnect the active Wi-Fi interface as reported by nmcli."""
    active_runner = runner or _DEFAULT_RUNNER

    status = _run_nmcli(
        ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"],
        timeout=5,
        timeout_message="Timed out while querying active devices",
        runner=active_runner,
    )

    wifi_rows: list[tuple[str, str]] = []
    for line in status.stdout.strip().splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        device, dev_type, state = parts[0].strip(), parts[1].strip().lower(), parts[2].strip().lower()
        if dev_type == "wifi" and device:
            wifi_rows.append((device, state))

    if not wifi_rows:
        raise RuntimeError("No Wi-Fi device found to disconnect")

    active_states = {"connected", "connecting", "disconnecting"}
    wifi_device = next((device for device, state in wifi_rows if state in active_states), wifi_rows[0][0])

    return _run_nmcli(
        ["nmcli", "device", "disconnect", wifi_device],
        timeout=10,
        timeout_message=f"Timed out while disconnecting device {wifi_device}",
        runner=active_runner,
    )
