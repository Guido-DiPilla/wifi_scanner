#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Wi-Fi Scanner — A real-time Wi-Fi network scanner.
Requires: nmcli (NetworkManager), Python 3.8+, customtkinter
Install deps: pip install customtkinter
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Callable, Literal
from pathlib import Path
import customtkinter as ctk
import tkinter as tk
from PIL import Image
import help
from wifi_core.connection_service import (
    connect_to_network,
    disconnect_current_device,
)
from wifi_core.models import WifiNetwork
from wifi_core.scanner_service import get_saved_password, scan_wifi
from wifi_core.vendor_lookup import refresh_authoritative_ieee_cache, reload_vendor_database
from config import (
    __version__,
    ACCENT,
    ACCENT_HOVER,
    BG_CARD,
    BG_DARK,
    BG_HOVER,
    BG_ROW,
    BORDER,
    DEFAULT_SCAN_INTERVAL,
    DETAIL_PANEL_WIDTH,
    FONT_BODY,
    GREEN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MIN_WINDOW_WIDTH,
    RED_COL,
    TEXT_DIM,
    TEXT_MAIN,
    TOPBAR_HEIGHT,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    YELLOW,
)
from ui_widgets import DetailPanel, NetworkRow, StatsPanel
from ui_fonts import fira_font as _fira_font_fn, barlow_font as _barlow_font_fn
from ui_utils import bind_mousewheel_scrolling
from ui_dialogs import (
    show_adapter_info,
    show_error_dialog,
    show_hidden_network_dialog,
    show_network_context_menu,
    show_password_dialog,
)


SCAN_WATCHDOG_TIMEOUT_S = 45
SCAN_BUTTON_GLYPH = "⭮"


def format_found_count_status(total: int) -> str:
    """Format status text for unfiltered network count."""
    return f"{total} network{'s' if total != 1 else ''} found"


def format_filter_status(total: int, visible: int, query: str) -> str:
    """Format status text for filtered or unfiltered list views."""
    clean_query = query.strip()
    if not clean_query:
        return format_found_count_status(total)
    return f'Showing {visible} of {total} for "{clean_query}"'


def format_countdown_status(total: int, visible: int, query: str, remaining: int) -> str:
    """Format countdown status while auto-refresh is enabled."""
    clean_query = query.strip()
    if not clean_query:
        return f"{total} network{'s' if total != 1 else ''} · next scan in {remaining}s"
    return f'Showing {visible} of {total} for "{clean_query}" · next scan in {remaining}s'


def scan_watchdog_timed_out(started_at: float | None, now: float, timeout_s: int) -> bool:
    """Return True when a scan has exceeded the watchdog timeout."""
    if started_at is None:
        return False
    return (now - started_at) >= timeout_s


def should_disconnect_before_targeted_connect(
    current_bssid: str | None,
    target_bssid: str | None,
) -> bool:
    """Return True when switching to a different explicit AP target."""
    if not current_bssid or not target_bssid:
        return False
    return current_bssid != target_bssid


def prune_signal_history(
    history: dict[str, deque[tuple[float, int]]],
    *,
    active_bssids: set[str],
    selected_bssid: str | None,
    max_bssids: int = 400,
) -> None:
    """Prune stale signal history entries and cap total tracked BSSIDs.

    Keeps currently active BSSIDs and the currently selected BSSID (if any).
    If entries still exceed *max_bssids*, removes the oldest non-selected entries.
    """
    retained = set(active_bssids)
    if selected_bssid:
        retained.add(selected_bssid)

    for bssid in list(history):
        if bssid not in retained:
            del history[bssid]

    excess = len(history) - max_bssids
    if excess <= 0:
        return

    protected = {selected_bssid} if selected_bssid in history else set()
    candidates: list[tuple[float, str]] = []
    for bssid, samples in history.items():
        if bssid in protected:
            continue
        last_seen = samples[-1][0] if samples else 0.0
        candidates.append((last_seen, bssid))
    candidates.sort(key=lambda row: row[0])

    for _last_seen, bssid in candidates[:excess]:
        history.pop(bssid, None)


class WifiScannerApp(ctk.CTk):
    """Main application window coordinating scanning, rendering, and actions."""

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Wi-Fi Scanner")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(MIN_WINDOW_WIDTH, WINDOW_HEIGHT)
        self.configure(fg_color=BG_DARK)

        self._networks: list[WifiNetwork] = []
        self._selected_bssid: str | None = None  # track by BSSID, not by list index
        self._row_widgets: dict[str, NetworkRow] = {}
        self._scanning = False
        self._sort_col = "signal"
        self._sort_rev = True
        self._filter_text = tk.StringVar()
        self._filter_text.trace_add("write", self._on_filter_change)
        self._auto_refresh = tk.BooleanVar(value=True)
        self._auto_interval = DEFAULT_SCAN_INTERVAL
        self._last_scan_time: float | None = None
        self._countdown_job = None
        self._scan_watchdog_job = None
        self._scan_started_at: float | None = None
        self._vendor_refresh_in_flight = False
        self._dismiss_context_menu: Callable[[], None] = lambda: None
        # BSSID → deque of (timestamp, signal%) — capped at 60 samples (~30 min at 30 s)
        self._signal_history: dict[str, deque[tuple[float, int]]] = {}

        self._build_ui()
        self._setup_keyboard_shortcuts()
        self._start_scan()
        self.after_idle(self._start_vendor_db_refresh)

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        """Build the top bar, list area, stats panel, and detail panel."""
        topbar = self._build_topbar()
        self._build_topbar_title(topbar)
        self._build_topbar_controls(topbar)

        main = self._build_main_area()
        self._build_stats_panel(main)
        self._build_list_panel(main)
        self._build_detail_panel(main)

    def _build_topbar(self) -> ctk.CTkFrame:
        """Create and return the fixed top toolbar container."""
        topbar = ctk.CTkFrame(self, fg_color=BG_CARD, height=TOPBAR_HEIGHT, corner_radius=0)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)
        return topbar

    def _build_topbar_title(self, topbar: ctk.CTkFrame):
        """Render the app icon, title, and version text in the top bar."""
        # Load wifi icon
        icon_path = Path(__file__).parent / "wifi.png"
        if icon_path.exists():
            wifi_image = ctk.CTkImage(
                light_image=Image.open(icon_path),
                dark_image=Image.open(icon_path),
                size=(24, 24)
            )
            icon_label = ctk.CTkLabel(topbar, image=wifi_image, text="")
            icon_label.pack(side="left", padx=(20, 8), pady=16)

        title_frame = ctk.CTkFrame(topbar, fg_color="transparent")
        title_frame.pack(side="left", padx=(0, 20), pady=8)

        ctk.CTkLabel(
            title_frame, text="WI-FI SCANNER",
            font=_barlow_font_fn(22),
            text_color=ACCENT, height=28
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame, text=f"version: {__version__}",
            font=_fira_font_fn(10),
            text_color=TEXT_DIM, height=14
        ).pack(anchor="w")

    def _build_topbar_controls(self, topbar: ctk.CTkFrame):
        """Render filter, refresh, and help controls in the top bar."""
        # Search bar
        self._search_entry = ctk.CTkEntry(
            topbar, textvariable=self._filter_text,
            placeholder_text="Filter networks…",
            width=360, height=32,
            font=_fira_font_fn(11),
            fg_color=BG_DARK, border_color=BORDER,
            text_color=TEXT_MAIN, placeholder_text_color=TEXT_DIM
        )
        self._search_entry.pack(side="left", padx=(0, 6), pady=12)

        search_btn = ctk.CTkButton(
            topbar,
            text="🔍",
            font=_fira_font_fn(17, "bold"),
            width=34,
            height=32,
            fg_color=BG_ROW,
            text_color=ACCENT,
            hover_color=BG_HOVER,
            border_width=1,
            border_color=BORDER,
            corner_radius=6,
            anchor="se",
            command=lambda: (self._search_entry.focus_set(), self._on_filter_change()),
        )
        search_btn.pack(side="left", padx=(0, 10), pady=12)

        # Help button - centered in window using place()
        help_btn = ctk.CTkButton(
            topbar, text="Help",
            font=_fira_font_fn(15, "bold"),
            width=60, height=32,
            fg_color=BG_ROW, text_color=ACCENT,
            hover_color=BG_HOVER,
            border_width=1, border_color=BORDER,
            corner_radius=6,
            command=self._show_help
        )
        help_btn.place(relx=0.5, rely=0.5, anchor="center")

        # Auto-refresh toggle
        self._auto_label = ctk.CTkLabel(
            topbar, text="Auto-refresh",
            font=_fira_font_fn(10),
            text_color=TEXT_DIM
        )
        self._auto_label.pack(side="right", padx=(0, 10))

        auto_sw = ctk.CTkSwitch(
            topbar, variable=self._auto_refresh, text="",
            onvalue=True, offvalue=False, width=40,
            progress_color=ACCENT, button_color=TEXT_MAIN
        )
        auto_sw.pack(side="right", padx=(0, 4))

        self._scan_btn = ctk.CTkButton(
            topbar, text=f"{SCAN_BUTTON_GLYPH}\u2005Scan",
            font=_fira_font_fn(15, "bold"),
            width=90, height=32,
            fg_color=ACCENT, text_color=BG_DARK,
            hover_color=ACCENT_HOVER,
            command=self._start_scan
        )
        self._scan_btn.pack(side="right", padx=(0, 12))

        # Auto-refresh interval input
        interval_label = ctk.CTkLabel(
            topbar, text="sec",
            font=_fira_font_fn(10),
            text_color=TEXT_DIM
        )
        interval_label.pack(side="right", padx=(0, 4))

        self._interval_var = tk.StringVar(value=str(self._auto_interval))
        self._interval_entry = ctk.CTkEntry(
            topbar, textvariable=self._interval_var,
            width=45, height=32,
            font=_fira_font_fn(11),
            fg_color=BG_DARK, border_color=BORDER,
            text_color=TEXT_MAIN, justify="center"
        )
        self._interval_entry.pack(side="right", padx=(0, 4))
        self._interval_var.trace_add("write", self._on_interval_change)

        interval_title = ctk.CTkLabel(
            topbar, text="Interval:",
            font=_fira_font_fn(10),
            text_color=TEXT_DIM
        )
        interval_title.pack(side="right", padx=(0, 4))

        self._status_lbl = ctk.CTkLabel(
            topbar, text="",
            font=_fira_font_fn(10),
            text_color=TEXT_DIM
        )
        self._status_lbl.pack(side="right", padx=(0, 10))

    def _build_main_area(self) -> ctk.CTkFrame:
        """Create the main two-column layout container."""
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=12, pady=12)
        # Keep list column near its natural table width and give extra space to details.
        main.columnconfigure(0, weight=0, minsize=760)
        main.columnconfigure(1, weight=1, minsize=DETAIL_PANEL_WIDTH)
        main.rowconfigure(0, weight=0)
        main.rowconfigure(1, weight=1)
        return main

    def _build_stats_panel(self, main: ctk.CTkFrame):
        """Create and place the summary statistics panel."""
        self._stats_panel = StatsPanel(main, on_adapter_info=self._show_adapter_info)
        self._stats_panel.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

    def _build_list_panel(self, main: ctk.CTkFrame):
        """Create the network table area and attach scrolling behavior."""
        list_frame = ctk.CTkFrame(main, fg_color="transparent")
        list_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        list_frame.rowconfigure(1, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self._build_list_headers(list_frame)

        # Scrollable list
        self._list_canvas = tk.Canvas(list_frame, bg=BG_DARK, highlightthickness=0)
        scrollbar = ctk.CTkScrollbar(
            list_frame,
            command=self._list_canvas.yview,
            button_color=BORDER,
            button_hover_color=ACCENT,
        )
        self._list_inner = tk.Frame(self._list_canvas, bg=BG_DARK)

        self._list_canvas.create_window((0, 0), window=self._list_inner, anchor="nw")
        self._list_canvas.configure(yscrollcommand=scrollbar.set)

        self._list_canvas.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

        self._list_inner.bind(
            "<Configure>",
            lambda _e: self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all")),
        )

        # Linux wheel events do not bubble consistently from child rows.
        bind_mousewheel_scrolling(list_frame, self._scroll_list_from_event)

    def _build_list_headers(self, list_frame: ctk.CTkFrame):
        """Build sortable list column headers and bind click handlers."""
        header_frame = ctk.CTkFrame(list_frame, fg_color=BG_CARD, corner_radius=6)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        header_inner = tk.Frame(header_frame, bg=BG_CARD)
        header_inner.pack(fill="x", padx=12, pady=12)

        # Dot placeholder (no sort key)
        tk.Label(header_inner, text="", width=2, bg=BG_CARD).pack(side="left", padx=(0, 4))

        # Build sortable column headers and keep widget refs so _update_sort_headers()
        # can repaint the active column without rebuilding the whole header bar.
        col_defs: list[tuple[str, str, int, Literal["w", "center"], int | tuple[int, int], int]] = [
            ("SSID", "ssid", 28, "w", 8, 8),
            ("Signal", "signal", 12, "center", (25, 8), 8),
            ("Band", "band", 8, "center", (4, 8), 8),
            ("Ch", "channel", 4, "center", (16, 8), 8),
            ("Security", "security", 13, "w", 3, 8),
            ("Rate", "rate", 12, "w", (16, 8), 8),
        ]
        self._hdr_labels: dict[str, tk.Label] = {}
        for text, key, width, anchor, padx, _pady in col_defs:
            label = tk.Label(
                header_inner,
                text=text,
                width=width,
                font=(FONT_BODY, 11, "bold"),
                fg=ACCENT if self._sort_col == key else TEXT_DIM,
                bg=BG_CARD,
                cursor="hand2",
                anchor=anchor,
            )
            label.pack(side="left", padx=padx)

            def on_header_click(_event, sort_key: str = key):
                self._set_sort(sort_key)

            label.bind("<Button-1>", on_header_click)
            self._hdr_labels[key] = label

    def _build_detail_panel(self, main: ctk.CTkFrame):
        """Create and place the network detail panel."""
        self._detail = DetailPanel(main, width=DETAIL_PANEL_WIDTH)
        self._detail.grid(row=1, column=1, sticky="nsew")

    # ── Rendering ────────────────────────────────────────────────────────────

    _SORT_KEYS: dict[str, Any] = {
        "signal":   lambda n: n.signal,
        "ssid":     lambda n: n.ssid.lower(),
        "band":     lambda n: n.band,
        "channel":  lambda n: n.channel.zfill(3),
        "security": lambda n: n.security,
        "rate":     lambda n: n.rate,
    }

    def _get_sort_key(self, net: WifiNetwork):
        """Return sort key for the active sort column."""
        return self._SORT_KEYS.get(self._sort_col, lambda n: n.signal)(net)

    def _matches_filter(self, net: WifiNetwork, query: str) -> bool:
        """Return True when a network matches the active search query."""
        if not query:
            return True
        return (
            query in net.ssid.lower()
            or query in net.bssid.lower()
            or query in net.security.lower()
            or query in net.band.lower()
        )

    def _visible_networks(self) -> list[WifiNetwork]:
        """Return filtered and sorted networks for the current UI state."""
        query = self._filter_text.get().lower()
        filtered = [n for n in self._networks if self._matches_filter(n, query)]
        return sorted(filtered, key=self._get_sort_key, reverse=self._sort_rev)

    def _find_network_by_bssid(
        self,
        bssid: str | None,
        networks: list[WifiNetwork] | None = None,
    ) -> WifiNetwork | None:
        """Find a network by BSSID in the provided list or current state."""
        if not bssid:
            return None
        candidates = networks if networks is not None else self._networks
        return next((n for n in candidates if n.bssid == bssid), None)

    def _render_list(self):
        """Rebuild the visible network row widgets from filtered data."""
        for w in self._list_inner.winfo_children():
            w.destroy()
        self._row_widgets = {}

        nets = self._visible_networks()

        if not nets:
            filter_query = self._filter_text.get().strip()
            if not self._networks:
                empty_text = "No networks detected yet.\nPress Scan or wait for auto-refresh."
            elif filter_query:
                empty_text = (
                    f'No matches for "{filter_query}".\n'
                    "Clear the filter or try a broader term."
                )
            else:
                empty_text = "No networks available right now.\nPress Scan to try again."

            tk.Label(
                self._list_inner,
                text=empty_text,
                font=(FONT_BODY, 12),
                fg=TEXT_DIM,
                bg=BG_DARK,
                justify="center",
                wraplength=540,
            ).pack(expand=True, pady=40)
            return

        for i, net in enumerate(nets):
            self._build_network_row(net, i)

    def _build_network_row(self, net: WifiNetwork, idx: int) -> None:
        """Instantiate and register one table row for a network."""
        row = NetworkRow(
            self._list_inner,
            net=net,
            idx=idx,
            is_selected=(net.bssid == self._selected_bssid),
            on_select=self._on_network_select,
            on_right_click=self._show_context_menu,
        )
        self._row_widgets[net.bssid] = row

    def _on_network_select(self, _event, net: WifiNetwork) -> None:
        """Handle row selection and refresh details for the chosen network."""
        prev_bssid = self._selected_bssid
        self._selected_bssid = net.bssid
        self._refresh_selection_highlight(prev_bssid)
        self._show_network_details(net)

    def _show_network_details(self, net: WifiNetwork) -> None:
        """Render selected network details and matching signal history."""
        self._detail.show(net)
        self._detail.update_signal_history(list(self._signal_history.get(net.bssid, [])))

    def _set_row_selected(self, bssid: str, selected: bool) -> None:
        """Toggle selected state for a rendered row, if present."""
        row = self._row_widgets.get(bssid)
        if row:
            row.set_selected(selected)

    def _refresh_selection_highlight(self, previous_bssid: str | None = None) -> None:
        """Update row highlight state after selection changes."""
        if previous_bssid and previous_bssid != self._selected_bssid:
            self._set_row_selected(previous_bssid, False)
        if self._selected_bssid:
            self._set_row_selected(self._selected_bssid, True)

    # ── Keyboard Shortcuts ───────────────────────────────────────────────────

    def _setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts for the application."""
        # Ctrl+R: Manual refresh
        self.bind("<Control-r>", lambda e: self._start_scan())
        self.bind("<Control-R>", lambda e: self._start_scan())

        # Ctrl+F: Focus search box
        self.bind("<Control-f>", lambda e: self._focus_search())
        self.bind("<Control-F>", lambda e: self._focus_search())

        # Arrow keys: Navigate network list
        self.bind("<Up>", lambda e: self._navigate_list(-1))
        self.bind("<Down>", lambda e: self._navigate_list(1))

        # Enter: View details of selected network
        self.bind("<Return>", lambda e: self._show_selected_details())
        self.bind("<KP_Enter>", lambda e: self._show_selected_details())

    def _focus_search(self):
        """Focus the search entry box."""
        self._search_entry.focus_set()
        self._search_entry.select_range(0, tk.END)

    def _navigate_list(self, direction: int):
        """Navigate the network list with arrow keys."""
        nets = self._visible_networks()

        if not nets:
            return

        # Find current position of selected network (if any)
        current_index = 0
        if self._selected_bssid:
            for i, n in enumerate(nets):
                if n.bssid == self._selected_bssid:
                    current_index = i
                    break

        # Update selection index
        new_index = max(0, min(len(nets) - 1, current_index + direction))
        selected_net = nets[new_index]
        prev_bssid = self._selected_bssid
        self._selected_bssid = selected_net.bssid
        self._refresh_selection_highlight(prev_bssid)

        # Show details (this provides visual feedback without refreshing the list)
        self._show_network_details(selected_net)

    def _show_selected_details(self):
        """Show details of the currently selected network."""
        selected = self._find_network_by_bssid(self._selected_bssid)
        if selected is not None:
            self._show_network_details(selected)

    # ── Help Dialog ──────────────────────────────────────────────────────────

    def _show_help(self):
        """Display help dialog with app features and usage."""
        help.show_help(self)

    def _show_adapter_info(self):
        """Open the adapter capabilities dialog."""
        show_adapter_info(self)

    # ── Scanning ─────────────────────────────────────────────────────────────

    def _start_scan(self):
        """Trigger a background Wi-Fi scan if one is not already running."""
        if self._scanning:
            return

        self._scanning = True
        self._scan_started_at = time.time()
        self._set_scan_button_scanning()
        self._set_status_text("Scanning…", RED_COL)
        if self._countdown_job:
            self.after_cancel(self._countdown_job)
            self._countdown_job = None
        if self._scan_watchdog_job:
            self.after_cancel(self._scan_watchdog_job)
        self._scan_watchdog_job = self.after(
            SCAN_WATCHDOG_TIMEOUT_S * 1000,
            self._on_scan_watchdog_timeout,
        )
        self._start_background_task(self._do_scan)

    def _on_scan_watchdog_timeout(self):
        """Recover UI state when a scan appears stuck past watchdog timeout."""
        self._scan_watchdog_job = None
        if not self._scanning:
            return
        if not scan_watchdog_timed_out(self._scan_started_at, time.time(), SCAN_WATCHDOG_TIMEOUT_S):
            return

        self._scanning = False
        self._scan_started_at = None
        self._set_scan_button_idle()
        self._set_status_text("Scan timed out. Retrying on next interval.", RED_COL)
        if self._auto_refresh.get():
            self._schedule_countdown()

    def _do_scan(self):
        """Run scan service on a worker thread and marshal result to UI thread."""
        try:
            networks = scan_wifi()
            self._post_scan_result(networks, None)
        except RuntimeError as e:
            self._post_scan_result([], str(e))
        except Exception as e:  # pragma: no cover - defensive fallback path
            self._post_scan_result([], f"Unexpected scan error: {e}")

    def _post_scan_result(self, networks: list[WifiNetwork], error: str | None) -> None:
        """Marshal scan result handling back to the UI thread."""
        self.after(0, self._on_scan_complete, networks, error)

    def _on_scan_complete(self, networks: list[WifiNetwork], error: str | None):
        """Apply scan results, refresh UI state, and schedule next auto scan."""
        self._finalize_scan_cycle()

        if error:
            self._show_scan_error(error)
        else:
            self._apply_scan_results(networks)

        if self._auto_refresh.get():
            self._schedule_countdown()

    def _finalize_scan_cycle(self) -> None:
        """Reset scan-in-progress state and restore scan controls."""
        if self._scan_watchdog_job:
            self.after_cancel(self._scan_watchdog_job)
            self._scan_watchdog_job = None
        self._scanning = False
        self._scan_started_at = None
        self._set_scan_button_idle()
        self._last_scan_time = time.time()

    def _set_scan_button_scanning(self) -> None:
        """Apply visual state for an in-progress scan."""
        self._scan_btn.configure(text="Scanning…", text_color=RED_COL, fg_color=BG_ROW)

    def _set_scan_button_idle(self) -> None:
        """Apply visual state for an idle/manual scan button."""
        self._scan_btn.configure(text=f"{SCAN_BUTTON_GLYPH}\u2005Scan", text_color=BG_DARK, fg_color=ACCENT)

    def _show_scan_error(self, error: str) -> None:
        """Show a truncated scan error message in the status bar."""
        self._set_status_text(f"Error: {error[:60]}", RED_COL)

    def _apply_scan_results(self, networks: list[WifiNetwork]) -> None:
        """Store networks, refresh panels, and update selected details."""
        self._networks = networks
        self._set_status_text(format_found_count_status(len(networks)), TEXT_DIM)
        self._stats_panel.refresh(networks)
        self._render_list()
        self._update_filter_status()
        self._record_signal_history(networks)
        self._refresh_selected_network_details(networks)

    def _record_signal_history(self, networks: list[WifiNetwork]) -> None:
        """Append latest signal samples and prune stale BSSID history."""
        now = time.time()
        for net in networks:
            if net.bssid not in self._signal_history:
                self._signal_history[net.bssid] = deque(maxlen=60)
            self._signal_history[net.bssid].append((now, net.signal))
        prune_signal_history(
            self._signal_history,
            active_bssids={n.bssid for n in networks},
            selected_bssid=self._selected_bssid,
        )

    def _refresh_selected_network_details(self, networks: list[WifiNetwork]) -> None:
        """Refresh the detail panel when the selected BSSID remains visible."""
        selected = self._find_network_by_bssid(self._selected_bssid, networks)
        if selected is None:
            return
        self._show_network_details(selected)

    def _schedule_countdown(self):
        """Update next-scan countdown once per second while auto-refresh is on."""
        if self._countdown_job:
            self.after_cancel(self._countdown_job)

        def tick():
            if not self._auto_refresh.get() or self._scanning:
                return
            elapsed = time.time() - (self._last_scan_time or 0)
            remaining = max(0, self._auto_interval - int(elapsed))
            total = len(self._networks)
            query = self._filter_text.get()
            visible = len(self._visible_networks())
            self._set_status_text(
                format_countdown_status(total, visible, query, remaining),
                TEXT_DIM,
            )
            if remaining <= 0:
                self._start_scan()
            else:
                self._countdown_job = self.after(1000, tick)

        self._countdown_job = self.after(1000, tick)

    def _start_background_task(self, target: Callable[[], None]) -> None:
        """Run a no-arg callable on a daemon worker thread."""
        threading.Thread(target=target, daemon=True).start()

    def _start_vendor_db_refresh(self) -> None:
        """Refresh vendor mappings in the background after UI is visible."""
        if getattr(self, "_vendor_refresh_in_flight", False):
            return
        self._vendor_refresh_in_flight = True
        self._start_background_task(self._refresh_vendor_db_async)

    def _refresh_vendor_db_async(self) -> None:
        """Fetch latest IEEE mappings without blocking startup."""
        refreshed = False
        try:
            refreshed = refresh_authoritative_ieee_cache(force=True, timeout=30.0)
            if refreshed:
                reload_vendor_database(force_refresh=False)
        except Exception:
            refreshed = False

        self.after(0, self._on_vendor_db_refresh_complete, refreshed)

    def _on_vendor_db_refresh_complete(self, refreshed: bool) -> None:
        """Apply updated vendor mappings when background refresh succeeds."""
        self._vendor_refresh_in_flight = False
        if not refreshed:
            return

        self._invalidate_cached_vendor_names()
        self._render_list()
        self._refresh_selected_network_details(getattr(self, "_networks", []))
        self._update_filter_status()

    def _invalidate_cached_vendor_names(self) -> None:
        """Clear cached vendor properties so lookups use the refreshed database."""
        for net in getattr(self, "_networks", []):
            net.__dict__.pop("vendor", None)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_sort_headers(self):
        """Repaint column header labels to reflect the active sort column."""
        for key, label in self._hdr_labels.items():
            try:
                label.configure(fg=ACCENT if key == self._sort_col else TEXT_DIM)
            except tk.TclError:
                pass

    def _set_sort(self, col: str):
        """Set or toggle list sort order, then re-render visible rows."""
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = col == "signal"
        self._update_sort_headers()
        self._render_list()

    def _update_filter_status(self):
        """Show filter match counts without overriding active scan status."""
        if self._scanning:
            return

        query = self._filter_text.get()
        total = len(self._networks)
        visible = len(self._visible_networks())
        self._set_status_text(format_filter_status(total, visible, query), TEXT_DIM)

    def _on_filter_change(self, *args):
        """Re-render list and show query-aware match counts."""
        self._render_list()
        self._update_filter_status()

    def _on_interval_change(self, *args):
        """Update auto-refresh interval when user changes the input."""
        try:
            value = self._interval_var.get().strip()
            if value:
                interval = int(value)
                if MIN_SCAN_INTERVAL <= interval <= MAX_SCAN_INTERVAL:
                    self._auto_interval = interval
        except ValueError:
            pass

    # ── Quick Connect ────────────────────────────────────────────────────────

    def _show_context_menu(self, event, net: WifiNetwork) -> None:
        """Show themed right-click menu for network actions."""
        self._dismiss_context_menu()
        self._dismiss_context_menu = show_network_context_menu(
            self, event, net,
            on_connect=lambda: self._connect_to_network(net),
            on_disconnect=lambda: self._disconnect_network(net),
            on_hidden_connect=self._connect_to_hidden_network,
        )


    def _connect_to_network(self, net: WifiNetwork):
        """Connect to a WiFi network using NetworkManager."""
        # Fast path: reuse the password already resolved by the detail panel,
        # avoiding a redundant nmcli subprocess call.
        cached = self._detail.get_cached_password(net.bssid)
        if cached is not None:
            self._on_saved_password_lookup(net, cached)
            return

        self._show_connection_status(f"Preparing connection to {net.ssid}...", None)

        def worker():
            saved_password = get_saved_password(net.ssid)
            self.after(0, lambda: self._on_saved_password_lookup(net, saved_password))

        self._start_background_task(worker)

    def _on_saved_password_lookup(self, net: WifiNetwork, saved_password: str):
        if not saved_password and ("WPA" in net.security or "WEP" in net.security):
            self._show_password_dialog(net)
        else:
            self._do_connect(net.ssid, net.bssid, saved_password or None, net.device or None)

    def _show_password_dialog(self, net: WifiNetwork):
        """Open the password prompt dialog for a protected network."""
        show_password_dialog(
            self,
            net,
            lambda ssid, bssid, password: self._do_connect(
                ssid,
                bssid,
                password,
                net.device or None,
            ),
        )

    def _run_async_nm_action(
        self,
        action: Callable[[], Any],
        *,
        in_progress_message: str,
        success_message: str,
        failure_prefix: str,
        failure_title: str,
        exception_status: str,
        exception_title: str,
        on_success: Callable[[], None] | None = None,
        success_refresh_delay_ms: int | None = None,
        failure_refresh_delay_ms: int | None = None,
        on_failure: Callable[[str], bool] | None = None,
    ):
        """Execute a NetworkManager action asynchronously and handle UI updates."""
        def worker():
            try:
                result = action()
                if result.returncode == 0:
                    self._handle_nm_action_success(
                        success_message=success_message,
                        on_success=on_success,
                        refresh_delay_ms=success_refresh_delay_ms,
                    )
                    return

                error_msg = result.stderr.strip() or result.stdout.strip() or "Operation failed"
                self._handle_nm_action_failure(
                    error_msg=error_msg,
                    failure_prefix=failure_prefix,
                    failure_title=failure_title,
                    refresh_delay_ms=failure_refresh_delay_ms,
                    on_failure=on_failure,
                )
            except RuntimeError as e:
                self._handle_nm_action_exception(
                    exc=e,
                    exception_status=exception_status,
                    exception_title=exception_title,
                    refresh_delay_ms=failure_refresh_delay_ms,
                )
            except Exception as e:  # pragma: no cover - defensive fallback path
                self._handle_nm_action_exception(
                    exc=RuntimeError(f"Unexpected connection error: {e}"),
                    exception_status=exception_status,
                    exception_title=exception_title,
                    refresh_delay_ms=failure_refresh_delay_ms,
                )

        self._start_background_task(worker)
        self._show_connection_status(in_progress_message, None)

    def _schedule_scan_refresh(self, delay_ms: int | None) -> None:
        """Schedule a scan refresh when a delay is provided."""
        if delay_ms is not None:
            self.after(delay_ms, self._start_scan)

    def _handle_nm_action_success(
        self,
        *,
        success_message: str,
        on_success: Callable[[], None] | None,
        refresh_delay_ms: int | None,
    ) -> None:
        """Handle successful completion of an async nmcli action."""
        self._queue_connection_status(success_message, True)
        if on_success is not None:
            self.after(0, on_success)
        self._schedule_scan_refresh(refresh_delay_ms)

    def _handle_nm_action_failure(
        self,
        *,
        error_msg: str,
        failure_prefix: str,
        failure_title: str,
        refresh_delay_ms: int | None,
        on_failure: Callable[[str], bool] | None,
    ) -> None:
        """Handle non-zero return results from an async nmcli action."""
        if on_failure is not None and on_failure(error_msg):
            return

        self._queue_connection_status(failure_prefix, False)
        self._queue_error_dialog(failure_title, error_msg)
        self._schedule_scan_refresh(refresh_delay_ms)

    def _handle_nm_action_exception(
        self,
        *,
        exc: RuntimeError,
        exception_status: str,
        exception_title: str,
        refresh_delay_ms: int | None,
    ) -> None:
        """Handle runtime exceptions raised by an async nmcli action."""
        self._queue_connection_status(exception_status, False)
        self._queue_error_dialog(exception_title, str(exc))
        self._schedule_scan_refresh(refresh_delay_ms)

    def _queue_connection_status(self, message: str, success: bool | None) -> None:
        """Schedule a connection status update on the UI thread."""
        self.after(0, lambda: self._show_connection_status(message, success))

    def _queue_error_dialog(self, title: str, message: str) -> None:
        """Schedule an error dialog after a short UI update delay."""
        self.after(100, lambda: self._show_error_dialog(title, message))

    def _show_error_dialog(self, title: str, message: str):
        show_error_dialog(self, title, message)

    def _active_connected_bssid(self) -> str | None:
        """Return currently connected BSSID from latest scan results, if known."""
        for net in self._networks:
            if net.in_use:
                return net.bssid
        return None

    def _do_connect(
        self,
        ssid: str,
        bssid: str | None,
        password: str | None,
        device: str | None = None,
    ):
        """Execute connection using nmcli device wifi connect."""

        force_handoff = should_disconnect_before_targeted_connect(
            self._active_connected_bssid(),
            bssid,
        )

        def action():
            if force_handoff:
                disconnect = disconnect_current_device()
                if disconnect.returncode != 0:
                    return disconnect
            return connect_to_network(ssid=ssid, bssid=bssid, password=password, device=device)

        self._run_async_nm_action(
            action,
            in_progress_message=(
                f"Switching to {ssid}..." if force_handoff else f"Connecting to {ssid}..."
            ),
            success_message=f"Connected to {ssid}",
            failure_prefix=f"Failed to connect to {ssid}",
            failure_title="Connection Failed",
            exception_status="Connection error",
            exception_title="Connection Error",
            success_refresh_delay_ms=2000,
            failure_refresh_delay_ms=1200,
        )

    def _disconnect_network(self, net: WifiNetwork):
        """Disconnect from current network."""

        self._run_async_nm_action(
            disconnect_current_device,
            in_progress_message=f"Disconnecting from {net.ssid}...",
            success_message=f"Disconnected from {net.ssid}",
            failure_prefix=f"Failed to disconnect from {net.ssid}",
            failure_title="Disconnection Failed",
            exception_status="Disconnection error",
            exception_title="Disconnection Error",
            success_refresh_delay_ms=1000,
            failure_refresh_delay_ms=1200,
        )

    def _connect_to_hidden_network(self):
        """Open the hidden-network connect dialog."""
        show_hidden_network_dialog(self, self._do_connect)

    def _show_connection_status(self, message: str, success: bool | None):
        """Show connection status in the status label."""
        if success is None:  # In progress
            color = YELLOW
        elif success:
            color = GREEN
        else:
            color = RED_COL

        self._set_status_text(message, color)

    def _set_status_text(self, message: str, color: str) -> None:
        """Update status label text and color through one shared path."""
        self._status_lbl.configure(text=message, text_color=color)

    def _scroll_units_from_event(self, event) -> int:
        """Normalize platform-specific wheel events into +/- unit steps."""
        if event.num == 4:
            return -1
        if event.num == 5:
            return 1

        delta = getattr(event, "delta", 0)
        if delta > 0:
            return -1
        if delta < 0:
            return 1
        return 0

    def _scroll_list_from_event(self, event):
        """Scroll the network list canvas from routed wheel events."""
        units = self._scroll_units_from_event(event)
        if units:
            self._list_canvas.yview_scroll(units, "units")
            return "break"
        return None


# Entry point

if __name__ == "__main__":
    try:
        app = WifiScannerApp()
        app.mainloop()
    except KeyboardInterrupt:
        pass
