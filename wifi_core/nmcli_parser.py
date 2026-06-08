# SPDX-License-Identifier: MIT
"""Parsing helpers for nmcli output."""

from __future__ import annotations

from wifi_core.models import WifiNetwork


def split_escaped(text: str, sep: str = ":") -> list[str]:
    """Split text by separator while honoring backslash escapes."""
    parts: list[str] = []
    buf: list[str] = []
    escaped = False

    for ch in text:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == sep:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)

    if escaped:
        buf.append("\\")
    parts.append("".join(buf))
    return parts


def _to_int(value: str, default: int = 0) -> int:
    """Safely cast to int, returning *default* on conversion failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_scan_line(line: str, timestamp: float) -> WifiNetwork | None:
    """Parse one nmcli scan line into a WifiNetwork object."""
    parts = split_escaped(line, ":")

    if len(parts) < 11:
        return None

    in_use = parts[0].strip() == "*"
    ssid = parts[1] if parts[1] else "<hidden>"
    bssid = parts[2]

    # Indices 3–10 are guaranteed to exist: the len < 11 guard above ensures it.
    mode = parts[3]
    channel = parts[4]
    freq = parts[5]
    rate = parts[6]
    signal = _to_int(parts[7], 0)
    bars = parts[8]
    security = parts[9] or "Open"
    bandwidth = parts[10] or "20 MHz"
    device = parts[11] if len(parts) > 11 else ""
    wpa_flags = parts[12] if len(parts) > 12 else ""
    rsn_flags = parts[13] if len(parts) > 13 else ""

    return WifiNetwork(
        ssid=ssid,
        bssid=bssid,
        mode=mode,
        channel=channel,
        frequency=freq,
        rate=rate,
        signal=signal,
        bars=bars,
        security=security,
        bandwidth=bandwidth,
        device=device,
        wpa_flags=wpa_flags,
        rsn_flags=rsn_flags,
        in_use=in_use,
        last_seen=timestamp,
        password="",
    )
