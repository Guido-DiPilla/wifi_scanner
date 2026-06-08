# SPDX-License-Identifier: MIT
"""
Help dialog for Wi-Fi Scanner application.
"""

import customtkinter as ctk
from pathlib import Path
from PIL import Image
from config import ACCENT, BG_CARD, BG_DARK, TEXT_MAIN
from ui_fonts import fira_font as _fira_font, barlow_font as _barlow_font
from ui_utils import enable_mousewheel_scrolling


def _add_section_title(parent, title: str, top_padding: int):
    """Render a section heading inside the help dialog."""
    ctk.CTkLabel(
        parent,
        text=title,
        font=_fira_font(14, "bold"),
        text_color=ACCENT,
        anchor="w",
    ).pack(fill="x", padx=15, pady=(top_padding, 5))


def _add_section_lines(parent, lines: list[str]):
    """Render each help bullet line as a left-aligned label."""
    for line in lines:
        ctk.CTkLabel(
            parent,
            text=line,
            font=_fira_font(11),
            text_color=TEXT_MAIN,
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=15, pady=2)

_HELP_SECTIONS: list[tuple[str, list[str]]] = [
    ("OVERVIEW", [
        "Desktop Wi-Fi scanner for Linux systems that use NetworkManager (nmcli).",
        "The app scans nearby networks, displays details, and provides connection actions."
    ]),
    ("SCANNING", [
        "- Manual scan plus optional auto-refresh (1-300 second interval)",
        "- Scan results are deduplicated by BSSID",
        "- Per-channel congestion counts are computed from current scan results",
        "- A scan watchdog timeout resets UI state if a scan stalls"
    ]),
    ("MAIN LIST", [
        "Columns in the list view:",
        "- Connected marker",
        "- SSID",
        "- Signal (bar plus percentage)",
        "- Band",
        "- Channel",
        "- Security",
        "- Rate",
        "List behavior:",
        "- Sorting by column header click",
        "- Live filtering by SSID, BSSID, security text, or band text",
        "- Keyboard navigation"
    ]),
    ("DETAIL PANEL", [
        "The detail panel shows properties for the selected network:",
        "- Connection state",
        "- BSSID",
        "- IPv4 and IPv6 addresses (for connected network/device)",
        "- DNS4 and DNS6 values",
        "- Optional public IP lookup (user-triggered toggle)",
        "- Signal percentage and estimated dBm",
        "- Signal history sparkline for the selected BSSID",
        "- Frequency, band, channel, and bandwidth",
        "- Max rate and estimated throughput",
        "- Mode, security classification, and encryption label",
        "- Saved password status for known connections",
        "- Vendor lookup from BSSID",
        "- Congestion count and quality score",
        "- Device and last seen time",
        "Saved password values are masked in the detail row and can be",
        "revealed from a temporary popup when available"
    ]),
    ("DETAIL PANEL SCROLLING", [
        "The detail panel supports:",
        "- Vertical scrolling for long content",
        "- Horizontal scrolling for long values",
        "- Dynamic layout updates when the window is resized"
    ]),
    ("CONNECTION ACTIONS", [
        "From the network context menu:",
        "- Connect to selected network",
        "- Disconnect current Wi-Fi device",
        "- Connect to hidden network",
        "Connection logic uses nmcli and runs asynchronously"
    ]),
    ("STATISTICS PANEL", [
        "Displays:",
        "- Total networks",
        "- Count by band (2.4 GHz, 5 GHz, and 6 GHz when present)",
        "- Secured vs open counts",
        "- Channel histogram for detected 2.4 GHz and 5 GHz channels"
    ]),
    ("ADAPTER INFORMATION DIALOG", [
        "Shows data returned by adapter service:",
        "- Device, mode, and PHY",
        "- Driver, driver version, and firmware version",
        "- Supported bands and inferred Wi-Fi standards",
        "- Transmit power and regulatory domain",
        "- Parsed capability flags",
        "If iw or ethtool is missing, the dialog reports missing tools",
        "and degraded fields"
    ]),
    ("KEYBOARD & MOUSE", [
        "- Click column headers to sort",
        "- Click a row to select and show details",
        "- Right-click a row to open connection actions",
        "- Type in the filter box for live filtering",
        "- Use the search button to focus filter and re-apply current query",
        "- Change interval value to adjust auto-refresh",
        "- Toggle Auto-refresh to enable or disable periodic scans",
        "- Click Scan for an immediate scan",
        "- Click Help to open this dialog"
    ]),
    ("VENDOR LOOKUP BEHAVIOR", [
        "Vendor resolution is local and source-priority based:",
        "- Wireshark manuf database (if present)",
        "- IEEE-style OUI text files (cache or system paths)",
        "Notes:",
        "- Cached IEEE files are read from ~/.cache/wifi_scanner/ieee/ when present",
        "- Normal lookups do not require network access",
        "- If no vendor source is available, value falls back to Unknown"
    ]),
    ("KEYBOARD SHORTCUTS", [
        "- Ctrl+R: Start scan",
        "- Ctrl+F: Focus filter field",
        "- Up Arrow / Down Arrow: Move selection through visible list",
        "- Enter: Show details for selected network"
    ]),
]


def show_help(parent):
    """Display help dialog with app features and usage."""
    help_window = ctk.CTkToplevel(parent)
    help_window.title("Wi-Fi Scanner Help")
    help_window.geometry("750x950")
    help_window.configure(fg_color=BG_DARK)

    # Make it modal - wait for window to be visible first
    help_window.transient(parent)

    # Title
    title_frame = ctk.CTkFrame(help_window, fg_color=BG_DARK)
    title_frame.pack(fill="x", padx=20, pady=(20, 10))

    # Load wifi icon for help dialog
    icon_path = Path(__file__).parent / "wifi.png"
    if icon_path.exists():
        wifi_image = ctk.CTkImage(
            light_image=Image.open(icon_path),
            dark_image=Image.open(icon_path),
            size=(28, 28)
        )
        icon_label = ctk.CTkLabel(title_frame, image=wifi_image, text="")
        icon_label.pack(side="left", padx=(0, 10))

    ctk.CTkLabel(
        title_frame,
        text="Wi-Fi Scanner Help",
        font=_barlow_font(28),
        text_color=ACCENT
    ).pack(side="left")

    # Scrollable frame for content
    scroll_frame = ctk.CTkScrollableFrame(
        help_window,
        fg_color=BG_CARD,
        corner_radius=8
    )
    scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    # Add all sections
    for title, lines in _HELP_SECTIONS:
        top_padding = 10 if title == "OVERVIEW" else 15
        _add_section_title(scroll_frame, title, top_padding)
        _add_section_lines(scroll_frame, lines)

    # Add some bottom padding
    ctk.CTkLabel(scroll_frame, text="", height=10).pack()

    # Enable mouse wheel and trackpad scrolling (after all content is added)
    enable_mousewheel_scrolling(scroll_frame)

    # Close button
    ctk.CTkButton(
        help_window,
        text="Close",
        font=_fira_font(12, "bold"),
        width=120, height=36,
        fg_color=ACCENT, text_color=BG_DARK,
        hover_color="#79b8ff",
        command=help_window.destroy
    ).pack(pady=(0, 20))
