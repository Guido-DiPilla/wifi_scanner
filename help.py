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
        "A comprehensive Wi-Fi network scanner for Ubuntu Linux with real-time scanning,",
        "detailed network information, and channel congestion histogram."
    ]),
    ("MAIN FEATURES", [
        "• Live Wi-Fi Scanning - Automatic refresh (customizable 1-300 seconds)",
        "• Real-time Search/Filter - Find networks by name or any field",
        "• Sortable Columns - Click any header to sort (signal, band, channel, etc.)",
        "• Detailed Network Info - Click any network for comprehensive details",
        "• Password Recovery - View saved passwords for known networks",
        "• Channel Distribution - Visual histogram showing network congestion",
        "• Vendor Detection - Identifies router manufacturer from MAC address",
        "• Adapter Information - View WiFi hardware capabilities (⚙ Adapter button)"
    ]),
    ("NETWORK INFORMATION", [
        "The detail panel (right side) shows:",
        "• Connection Status - 'Status: Connected' or 'Status: Not connected'",
        "• BSSID - Access point MAC address",
        "• IPv4 Address - Local address assigned to this device (connected networks only)",
        "• IPv6 Address - IPv6 address if available (connected networks only)",
        "• DNS4 / DNS6 - DNS servers configured by NetworkManager",
        "• Public IP - Your external IP address (toggle 'Show Public IP' to fetch)",
        "• Signal Strength - Percentage, dBm, quality rating",
        "• Signal History - Sparkline chart of signal strength across recent scans",
        "• Frequency & Band - 2.4/5/6 GHz classification",
        "• Channel & Bandwidth - Channel number and width (20/40/80/160 MHz)",
        "• Speed Info - Max rate and theoretical throughput",
        "• Security Details - WPA3/WPA2/WPA/WEP/Open with assessment",
        "• Password - For saved networks (click to reveal, copy button)",
        "• Vendor - Router manufacturer (Apple, TP-Link, Google, etc.)",
        "• Congestion - Networks on same channel (color-coded)",
        "• Quality Score - Overall rating 0-100",
        "• Device & Last Seen - Network adapter and detection time"
    ]),
    ("DETAIL PANEL SCROLLING", [
        "The detail panel is fully scrollable for viewing all information:",
        "• Vertical Scrolling - Use mouse wheel or trackpad to scroll up/down",
        "  through all network details",
        "• Horizontal Scrolling - Long fields (like vendor names) can be",
        "  scrolled left/right to view full text",
        "• Expandable - Panel automatically expands to show all available fields",
        "Tip: The detail panel is fully responsive and resizes smoothly",
        "as you adjust the window width."
    ]),
    ("CHANNEL DISTRIBUTION", [
        "The histogram shows how crowded each Wi-Fi channel is:",
        "• Green (1-3 networks) - Optimal, low interference",
        "• Yellow (4-5 networks) - Acceptable, moderate traffic",
        "• Red (6+ networks) - Congested, avoid if possible",
        "Use this to choose the best channel for your router.",
        "Best 2.4 GHz channels: 1, 6, and 11 (non-overlapping)"
    ]),
    ("STATISTICS PANEL", [
        "Displays real-time network counts:",
        "• Total Networks - All detected networks",
        "• Band Distribution - Count per frequency band",
        "• Security Overview - Secured vs open networks"
    ]),
    ("WIFI ADAPTER INFORMATION", [
        "Click the ⚙ Adapter button to view your WiFi hardware details:",
        "• Device name and interface mode",
        "• Driver name, version, and firmware version",
        "• Supported frequency bands (2.4/5/6 GHz)",
        "• Supported WiFi standards (802.11a/b/g/n/ac/ax/be)",
        "• Transmit power level (dBm)",
        "• Regulatory domain setting",
        "• Advanced capabilities (MU-MIMO, Beamforming, WPA3, OFDMA, etc.)",
        "Requires iw tool for full features (sudo apt install iw)",
        "Optional: ethtool for firmware version (sudo apt install ethtool)"
    ]),
    ("QUICK CONNECT", [
        "Right-click any network to access connection options:",
        "• Connect - Join the selected WiFi network",
        "• Disconnect - Leave current network (if connected)",
        "• Connect to Hidden Network - Join networks not broadcasting SSID",
        "Connection uses NetworkManager (nmcli) for native integration."
    ]),
    ("KEYBOARD & MOUSE", [
        "• Click column headers - Sort by that column",
        "• Click network row - View detailed information",
        "• Right-click network row - Show connection menu",
        "• Click password field - Show tooltip with copy button",
        "• Type in search box - Filter networks in real-time",
        "• Change interval input - Set auto-refresh delay (1-300 seconds)",
        "• Toggle Auto-refresh - Enable/disable automatic scanning",
        "• Click Scan button - Manually refresh network list",
        "• Click ⚙ Adapter button - View WiFi adapter information",
        "• Click Help button - Show this help dialog"
    ]),
    ("VENDOR DETECTION & DATABASE", [
        "Router manufacturer identification uses multiple data sources:",
        "Primary Source:",
        "  • Authoritative IEEE OUI registries downloaded from standards-oui.ieee.org",
        "  • Cached locally at ~/.cache/wifi_scanner/ieee/ for fast lookups",
        "Fallback Sources:",
        "  • System installed databases (wireshark-common, ieee-data)",
        "How it Works:",
        "  • MAC addresses are matched against OUI/OUI36/MAM/IAB registries",
        "  • Longest-prefix matching ensures accurate manufacturer identification",
        "  • Cache is used for convenience (automatically updated on demand)",
        "Manual Cache Refresh:",
        "  Delete the cache directory to force download of latest data:",
        "  rm -rf ~/.cache/wifi_scanner/ieee/"
    ]),
    ("KEYBOARD SHORTCUTS", [
        "• Ctrl+R - Manual refresh (same as clicking Scan button)",
        "• Ctrl+F - Focus search box and select text",
        "• Up Arrow - Navigate to previous network in list",
        "• Down Arrow - Navigate to next network in list",
        "• Enter - View details of selected network",
        "Tip: Use Up/Down arrows to quickly browse networks,",
        "then press Enter to see details without using the mouse."
    ]),
    ("TIPS & TRICKS", [
        "• Quality scores above 70 indicate excellent networks",
        "• WPA3 or WPA2 encryption is considered secure",
        "• Green bars in Channel Distribution = best channels",
        "• Lower congestion = better performance",
        "• 5 GHz typically faster but shorter range than 2.4 GHz",
        "• Hidden networks show as <hidden> in SSID column"
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
