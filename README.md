# Wi-Fi Scanner

Desktop Wi-Fi scanner for Linux systems that use NetworkManager (`nmcli`).

The application provides:
- Live scan results with optional auto-refresh.
- Network filtering and sortable columns.
- Per-network detail view (signal, security, vendor, IP/DNS, saved password state).
- Connection and disconnection actions through NetworkManager.
- Adapter capability view (when system tools are available).
- Channel distribution summary and basic congestion indicators.

## Platform And Dependencies

### Required
- Linux with NetworkManager and `nmcli`.
- Python 3.8+.
- Python packages listed in [requirements.txt](requirements.txt).

### Optional System Tools
- `iw` for full adapter capability reporting.
- `ethtool` for additional driver and firmware details.
- Vendor database packages for MAC/OUI lookup:
  - `wireshark-common` (preferred source: `manuf`), or
  - `ieee-data`.

## Installation

```bash
# From repository root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional system packages:

```bash
sudo apt install iw ethtool wireshark-common
# or install ieee-data instead of wireshark-common
```

## Run

```bash
source .venv/bin/activate
python wifi_scanner.py
```

Alternative launcher:

```bash
./run_wifi_scanner.sh
```

## What The App Does

### Scanning
- Runs `nmcli dev wifi list --rescan yes` in a background thread.
- Deduplicates results by BSSID.
- Computes per-channel congestion counts from current scan results.
- Supports manual scan and optional auto-refresh.
- Auto-refresh interval is configurable from 1 to 300 seconds.
- Includes a scan watchdog timeout to recover UI state if a scan stalls.

### Main List
Columns in the list view:
- Connected marker.
- SSID.
- Signal (bar plus percentage).
- Band.
- Channel.
- Security.
- Rate.

The list supports:
- Sorting by column header click.
- Live filtering by SSID, BSSID, security text, or band text.
- Keyboard navigation.

### Detail Panel
The detail panel shows properties for the selected network, including:
- Connection state.
- BSSID.
- IPv4 and IPv6 addresses (for connected network/device).
- DNS4 and DNS6 values.
- Optional public IP lookup (user-triggered toggle).
- Signal percentage and estimated dBm.
- Signal history sparkline for the selected BSSID.
- Frequency, band, channel, and bandwidth.
- Max rate and estimated throughput.
- Mode, security classification, and encryption label.
- Saved password status for known connections.
- Vendor lookup from BSSID.
- Congestion count and quality score.
- Device and last seen time.

Detail value fields are intentionally widened so long vendor/manufacturer names are visible without premature truncation.

The password value is masked in the detail row and can be revealed from a temporary popup when available.

### Connection Actions
From the network context menu:
- Connect to selected network.
- Disconnect current Wi-Fi device.
- Connect to hidden network.

Connection logic uses `nmcli` and runs asynchronously to keep the UI responsive.

### Statistics Panel
Displays:
- Total networks.
- Count by band (2.4 GHz, 5 GHz, and 6 GHz when present).
- Secured vs open counts.
- Channel histogram for detected 2.4 GHz and 5 GHz channels.

### Adapter Information Dialog
Shows data returned by adapter service, such as:
- Device name, MAC address, mode, and PHY.
- Driver, driver version, firmware version.
- Supported bands and standards (inferred from `iw`).
- Transmit power and regulatory domain.
- Detected advanced capability flags.

If `iw` or `ethtool` is missing, the dialog reports missing tools and degraded fields.

## Vendor Lookup Behavior

Vendor resolution is local and source-priority based:
1. Wireshark `manuf` database (if present).
2. IEEE-style OUI text files (cache or system paths).

Notes:
- The app reads cached IEEE files from `~/.cache/wifi_scanner/ieee/` when present.
- It does not require network access for normal lookups.
- If no vendor source is available, vendor values fall back to `Unknown`.

## Keyboard Shortcuts

- `Ctrl+R`: Start scan.
- `Ctrl+F`: Focus filter field.
- `Up` / `Down`: Move selection through visible list.
- `Enter`: Show details for selected network.

## Screenshots

- Main window: [wifi_scanner_screenshot.png](wifi_scanner_screenshot.png)
- Detail panel: [wifi_scanner_screenshot_2.png](wifi_scanner_screenshot_2.png)
- Adapter dialog: [wifi_scanner_adapter.png](wifi_scanner_adapter.png)

## Development

Run checks locally:

```bash
source .venv/bin/activate
pytest -q
mypy wifi_scanner.py wifi_core
```

Optional mutation testing pilot:

```bash
source .venv/bin/activate
mutmut run
mutmut results
```

Pre-push version bump workflow is configured through [scripts/auto_bump_version.py](scripts/auto_bump_version.py) and `.githooks/pre-push`.

## License

MIT License. See [LICENSE](LICENSE). Release bundles also include [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) for dependency license references.
