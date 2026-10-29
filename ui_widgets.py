# SPDX-License-Identifier: MIT
"""
ui_widgets.py — Reusable custom widget classes for the Wi-Fi Scanner UI.

Contains:
    SignalBar   — Animated mini signal-strength bar drawn on a tk.Canvas.
    DetailPanel — Right-side detail panel that shows info for a selected network.
"""
from __future__ import annotations

from collections import Counter
import threading
from typing import Any, Callable, Literal

import customtkinter as ctk
import tkinter as tk

from config import (
    ACCENT,
    BG_DARK,
    BG_CARD,
    BG_HOVER,
    BG_ROW,
    BORDER,
    COLOR_6GHZ,
    FONT_BODY,
    FOCUS_RING,
    FONT_TITLE,
    GREEN,
    MAX_SECURITY_DISPLAY,
    MAX_SSID_DISPLAY,
    RED_COL,
    ROW_SELECTED_BG,
    ROW_SELECTED_HOVER_BG,
    ROW_SELECTED_IN_USE_BG,
    STATS_HEIGHT,
    TEXT_DIM,
    TEXT_MAIN,
    YELLOW,
)
from ui_fonts import fira_font as _fira_font
from ui_utils import bind_mousewheel_scrolling
from wifi_core.models import WifiNetwork
from wifi_core.scanner_service import get_device_dns, get_device_ips, get_public_ip, get_saved_password
from wifi_core.vendor_lookup import is_system_manuf_loaded, system_manuf_path


class SignalBar(tk.Canvas):
    """Mini animated signal strength bar widget."""

    def __init__(self, parent, signal: int, color: str, **kwargs):
        bg_color = kwargs.pop('bg', BG_ROW)
        super().__init__(parent, width=48, height=18,
                         bg=bg_color, highlightthickness=0, **kwargs)
        self._draw(signal, color)

    def _draw(self, signal: int, color: str):
        """Render the bar graph based on the current signal percentage."""
        self.delete("all")
        num_bars = 4
        bar_w = 7
        gap = 3
        heights = [5, 9, 13, 17]
        filled = max(1, round((signal / 100) * num_bars))
        x = 2
        for i in range(num_bars):
            h = heights[i]
            y1 = 18 - h
            fill = color if i < filled else BORDER
            self.create_rectangle(x, y1, x + bar_w, 18, fill=fill, outline="")
            x += bar_w + gap


class SelectableText(tk.Text):
    """Read-only text widget that still supports selection and copy."""

    def __init__(
        self,
        parent,
        *,
        font: tuple[str, int] | tuple[str, int, str],
        text_color: str,
        bg_color: str,
        width: int,
        wrap: Literal["none", "char", "word"] = "word",
        min_lines: int = 1,
        max_lines: int = 4,
        auto_height: bool = False,
    ):
        super().__init__(
            parent,
            font=font,
            fg=text_color,
            bg=bg_color,
            wrap=wrap,
            width=width,
            height=min_lines,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            padx=0,
            pady=0,
            insertwidth=0,
            exportselection=True,
            cursor="xterm",
            takefocus=True,
            spacing1=0,
            spacing2=0,
            spacing3=0,
        )
        self._min_lines = min_lines
        self._max_lines = max_lines
        self._auto_height = auto_height
        self._font = font
        self._ctx_popup: tk.Toplevel | None = None
        self._ctx_popup_bind_ids: list[tuple[tk.Misc, str, str]] = []
        self.bind("<Button-1>", self._focus_for_selection, add="+")
        self.bind("<Button-3>", self._show_context_menu)
        self.bind("<Control-Button-1>", self._show_context_menu)
        self.bind("<Control-c>", self._copy_selection)
        self.bind("<Control-C>", self._copy_selection)
        self.bind("<Control-a>", self._select_all)
        self.bind("<Control-A>", self._select_all)
        self.configure(state="disabled")

    def _focus_for_selection(self, _event):
        """Ensure widget has focus before text selection starts."""
        self.focus_set()

    def _copy_selection(self, _event):
        """Handle Ctrl+C copy for selected text and consume the event."""
        self._copy_selected_text()
        return "break"

    def _show_context_menu(self, event):
        """Show the custom context menu with Copy and Select All actions."""
        self.focus_set()
        self._dismiss_context_menu()

        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        popup.configure(bg=BORDER)
        popup.geometry(f"+{event.x_root}+{event.y_root}")
        top = self.winfo_toplevel()
        try:
            popup.transient(top)
        except tk.TclError:
            pass
        self._ctx_popup = popup

        border_frame = ctk.CTkFrame(popup, fg_color=BORDER, corner_radius=8)
        border_frame.pack(fill="both", expand=True)

        content = ctk.CTkFrame(border_frame, fg_color=BG_ROW, corner_radius=7)
        content.pack(fill="both", expand=True, padx=1, pady=1)

        def add_item(label: str, action: Callable[[], None]):
            row = ctk.CTkFrame(content, fg_color=BG_ROW, corner_radius=6)
            row.pack(fill="x", pady=1)
            lbl = ctk.CTkLabel(
                row,
                text=label,
                font=(FONT_BODY, 11),
                text_color=TEXT_MAIN,
                fg_color="transparent",
                padx=16,
                pady=8,
                anchor="w",
            )
            lbl.pack(fill="x")
            row.configure(cursor="hand2")
            lbl.configure(cursor="hand2")

            def on_enter(_e):
                row.configure(fg_color=BG_HOVER)
                lbl.configure(text_color=ACCENT)

            def on_leave(_e):
                row.configure(fg_color=BG_ROW)
                lbl.configure(text_color=TEXT_MAIN)

            def on_click(_e, _action=action):
                self._dismiss_context_menu()
                self.focus_set()
                self.after_idle(_action)

            for widget in (row, lbl):
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)
                widget.bind("<Button-1>", on_click)

        add_item("Copy", self._copy_selected_text)
        add_item("Select All", self._select_all_command)

        popup.bind("<FocusOut>", lambda _e: self._dismiss_context_menu(), add="+")
        popup.bind("<Escape>", lambda _e: self._dismiss_context_menu(), add="+")
        for widget, sequence in ((self, "<Button-1>"), (top, "<Button-1>"), (top, "<Button-3>")):
            bind_id = widget.bind(sequence, lambda _e: self._dismiss_context_menu(), add="+")
            if bind_id:
                self._ctx_popup_bind_ids.append((widget, sequence, bind_id))

    def _dismiss_context_menu(self):
        """Dismiss the context menu and remove temporary global bindings."""
        for widget, sequence, bind_id in self._ctx_popup_bind_ids:
            try:
                widget.unbind(sequence, bind_id)
            except tk.TclError:
                pass
        self._ctx_popup_bind_ids.clear()

        popup = self._ctx_popup
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass
            self._ctx_popup = None

    def _copy_selected_text(self):
        """Copy the selected text range to the clipboard, if any."""
        if self.tag_ranges("sel"):
            self.clipboard_clear()
            self.clipboard_append(self.get("sel.first", "sel.last"))

    def _select_all_command(self):
        """Select the entire widget content and move insertion point to start."""
        self.focus_set()
        self.tag_add("sel", "1.0", "end-1c")
        self.mark_set("insert", "1.0")
        self.see("insert")

    def _select_all(self, _event):
        """Handle Ctrl+A selection and consume the event."""
        self.focus_set()
        self._select_all_command()
        return "break"

    def set_value(self, text: str, text_color: str | None = None):
        """Replace widget content and optionally override the foreground color."""
        self.configure(state="normal")
        self.configure(font=self._font)
        self.delete("1.0", "end")
        self.insert("1.0", text)
        if text_color is not None:
            self.configure(fg=text_color)
        self.configure(state="disabled")
        if self._auto_height:
            self.after_idle(self._adjust_height)

    def _adjust_height(self):
        """Auto-size widget height to fit visible wrapped lines."""
        text = self.get("1.0", "end-1c")
        if not text:
            display_lines = self._min_lines
        else:
            line_count = self.count("1.0", "end-1c", "displaylines")
            display_lines = int(line_count[0]) if line_count else self._min_lines
        self.configure(height=max(self._min_lines, min(display_lines, self._max_lines)))


class NetworkRow(tk.Frame):
    """Single network row widget with built-in hover/selection behavior."""

    def __init__(
        self,
        parent,
        *,
        net: WifiNetwork,
        idx: int,
        is_selected: bool,
        on_select: Callable[[tk.Event, WifiNetwork], None],
        on_right_click: Callable[[tk.Event, WifiNetwork], None],
    ):
        self.net = net
        self._on_select = on_select
        self._on_right_click = on_right_click

        self.base_bg = BG_CARD if idx % 2 == 0 else BG_ROW
        if net.in_use:
            self.base_bg = BG_DARK

        self.selected_bg = ROW_SELECTED_BG if not net.in_use else ROW_SELECTED_IN_USE_BG
        self.hover_bg = BG_HOVER
        self.selected_hover_bg = ROW_SELECTED_HOVER_BG
        self.selected = is_selected

        row_bg = self.selected_bg if self.selected else self.base_bg
        super().__init__(parent, bg=row_bg, cursor="hand2")
        self.pack(fill="x", pady=4, padx=2)

        self.indicator = tk.Frame(
            self,
            bg=ACCENT if self.selected else row_bg,
            width=6,
        )
        self.indicator.pack(side="left", fill="y")

        dot_text = "●" if net.in_use else " "
        dot_color = GREEN if net.in_use else row_bg
        self.dot = tk.Label(
            self,
            text=dot_text,
            fg=dot_color,
            bg=row_bg,
            font=(FONT_BODY, 11),
            width=2,
        )
        self.dot.pack(side="left", padx=(0, 4))

        ssid_display = net.ssid if len(net.ssid) <= MAX_SSID_DISPLAY else net.ssid[:MAX_SSID_DISPLAY - 2] + "…"
        tk.Label(
            self,
            text=ssid_display,
            fg=TEXT_MAIN,
            bg=row_bg,
            font=(FONT_BODY, 12, "bold"),
            width=28,
            anchor="w",
        ).pack(side="left", padx=8, pady=10)

        signal_frame = tk.Frame(self, bg=row_bg)
        signal_frame.pack(side="left", padx=8)
        SignalBar(signal_frame, net.signal, net.quality_color, bg=row_bg).pack(side="left", padx=(0, 6))
        tk.Label(
            signal_frame,
            text=f"{net.signal}%",
            fg=net.quality_color,
            bg=row_bg,
            font=(FONT_BODY, 12),
            width=4,
            anchor="e",
        ).pack(side="left")

        band_color = ACCENT if net.band == "5 GHz" else YELLOW if net.band == "2.4 GHz" else COLOR_6GHZ
        tk.Label(
            self,
            text=net.band,
            fg=band_color,
            bg=row_bg,
            font=(FONT_BODY, 12),
            width=8,
            anchor="center",
        ).pack(side="left", padx=8)

        tk.Label(
            self,
            text=net.channel,
            fg=TEXT_DIM,
            bg=row_bg,
            font=(FONT_BODY, 12),
            width=4,
            anchor="center",
        ).pack(side="left", padx=8)

        sec_text = net.security if net.security else "Open"
        sec_color = GREEN if "WPA" in sec_text else RED_COL if sec_text == "Open" else TEXT_DIM
        sec_display = sec_text[:MAX_SECURITY_DISPLAY] if len(sec_text) > MAX_SECURITY_DISPLAY else sec_text
        tk.Label(
            self,
            text=sec_display,
            fg=sec_color,
            bg=row_bg,
            font=(FONT_BODY, 12),
            width=13,
            anchor="w",
        ).pack(side="left", padx=3)

        tk.Label(
            self,
            text=net.rate,
            fg=TEXT_DIM,
            bg=row_bg,
            font=(FONT_BODY, 12),
            width=12,
            anchor="w",
        ).pack(side="left", padx=0)

        if self.selected:
            self.configure(
                highlightthickness=2,
                highlightbackground=FOCUS_RING,
                highlightcolor=FOCUS_RING,
                bd=0,
            )

        self._bind_descendants()

    def _bind_descendants(self) -> None:
        """Attach hover/select/right-click handlers to row and child widgets."""
        def on_enter(_event):
            self._set_hover(True)

        def on_leave(_event):
            self._set_hover(False)

        def on_click(event):
            self._on_select(event, self.net)

        def on_right_click(event):
            self._on_right_click(event, self.net)

        stack: list[tk.Misc] = [self]
        while stack:
            widget = stack.pop()
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)
            widget.bind("<Button-3>", on_right_click)
            stack.extend(widget.winfo_children())

    def _apply_background(self, bg: str) -> None:
        """Apply row background color while preserving indicator behavior."""
        for child in self.winfo_children():
            if child is self.indicator:
                continue
            try:
                child_widget: Any = child
                child_widget.configure(bg=bg)
            except tk.TclError:
                pass

        self.indicator.configure(bg=ACCENT if self.selected else bg)
        if not self.net.in_use:
            self.dot.configure(fg=bg)
        self.configure(bg=bg)

    def _set_hover(self, hovered: bool) -> None:
        """Switch row background between base, selected, and hover states."""
        bg = self.selected_hover_bg if (hovered and self.selected) else self.hover_bg if hovered else self.selected_bg if self.selected else self.base_bg
        self._apply_background(bg)

    def set_selected(self, selected: bool) -> None:
        """Update selected state and redraw row styling accordingly."""
        self.selected = selected
        if selected:
            self.configure(
                highlightthickness=2,
                highlightbackground=FOCUS_RING,
                highlightcolor=FOCUS_RING,
                bd=0,
            )
        else:
            self.configure(highlightthickness=0, bd=0)
        self._apply_background(self.selected_bg if selected else self.base_bg)


class SignalHistoryChart(tk.Canvas):
    """Sparkline showing signal strength history across recent scans."""

    _HEIGHT = 72
    _PAD_TOP = 8
    _PAD_BOT = 10
    _PAD_L = 6
    _PAD_R = 6

    def __init__(self, parent, **kwargs):
        """Initialize an empty chart and redraw when size changes."""
        super().__init__(
            parent,
            bg=BG_ROW,
            highlightthickness=0,
            height=self._HEIGHT,
            **kwargs,
        )
        self._data: list[tuple[float, int]] = []
        self.bind("<Configure>", lambda _e: self._redraw())

    def set_data(self, data: list[tuple[float, int]]) -> None:
        """Store chart samples and trigger a redraw."""
        self._data = list(data)
        self._redraw()

    def _redraw(self) -> None:
        """Render grid, area fill, line, and points for current samples."""
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return

        pt, pb, pl, pr = self._PAD_TOP, self._PAD_BOT, self._PAD_L, self._PAD_R
        ch = h - pt - pb  # chart height
        cw = w - pl - pr  # chart width

        # Subtle grid lines at 25 / 50 / 75 %
        for pct in (25, 50, 75):
            gy = pt + int(ch * (1 - pct / 100))
            self.create_line(pl, gy, w - pr, gy, fill=BORDER, width=1, dash=(3, 5))

        if not self._data:
            self.create_text(
                w // 2, h // 2,
                text="No history yet",
                fill=TEXT_DIM,
                font=(FONT_BODY, 9),
            )
            return

        n = len(self._data)
        signals = [s for _, s in self._data]

        def xp(i: int) -> float:
            return pl + (i * cw / (n - 1) if n > 1 else cw / 2)

        def yp(sig: int) -> float:
            return pt + ch * (1 - sig / 100)

        last = signals[-1]
        color = GREEN if last >= 70 else YELLOW if last >= 40 else RED_COL

        # Filled area under the curve (stippled for a dim effect)
        poly: list[float] = [pl, h - pb]
        for i, sig in enumerate(signals):
            poly += [xp(i), yp(sig)]
        poly += [xp(n - 1), h - pb]
        self.create_polygon(poly, fill=color, outline="", stipple="gray25")

        # Line
        if n >= 2:
            pts: list[float] = []
            for i, sig in enumerate(signals):
                pts += [xp(i), yp(sig)]
            self.create_line(pts, fill=color, width=2, smooth=True)

        # Dots — all small, last one slightly larger
        for i, sig in enumerate(signals):
            x, y = xp(i), yp(sig)
            r = 3.5 if i == n - 1 else 1.5
            self.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")


class DetailPanel(ctk.CTkFrame):
    """Right-side detail panel for a selected network."""

    def __init__(self, parent, **kwargs):
        """Initialize persistent detail widgets and placeholder overlay."""
        super().__init__(parent, fg_color=BG_CARD, corner_radius=12,
                         border_width=1, border_color=BORDER, **kwargs)
        self._current_password = ""
        self._current_net_bssid = ""
        self._password_resolved = False
        self._password_popup: tk.Toplevel | None = None
        self._password_popup_bind_ids: list[tuple[tk.Misc, str, str]] = []
        self._value_labels: dict[str, SelectableText] = {}
        self._current_net: WifiNetwork | None = None
        self._public_ip_var = tk.BooleanVar(value=False)

        # Build the full skeleton immediately; cover it with a placeholder
        # until the user selects a network for the first time.
        self._build_skeleton()
        self._placeholder = ctk.CTkLabel(
            self,
            text="Select a network\nto view details",
            font=ctk.CTkFont(FONT_BODY, 13),
            text_color=TEXT_DIM,
            fg_color=BG_CARD,
            justify="center",
        )
        self._placeholder.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _reset_transient(self):
        """Reset transient state without destroying skeleton widgets."""
        self._current_password = ""
        self._current_net_bssid = ""
        self._password_resolved = False
        self._clear_password_popup_bindings()
        if self._password_popup:
            self._password_popup.destroy()
            self._password_popup = None

    def _clear_password_popup_bindings(self) -> None:
        """Unbind temporary global handlers registered for password popup dismissal."""
        for widget, sequence, bind_id in self._password_popup_bind_ids:
            try:
                widget.unbind(sequence, bind_id)
            except tk.TclError:
                pass
        self._password_popup_bind_ids.clear()

    def _copy_password(self):
        """Copy password to clipboard."""
        if self._current_password:
            self.clipboard_clear()
            self.clipboard_append(self._current_password)
            self._hide_password_popup()

    def _show_password_popup(self, event):
        """Show password in a tooltip-style popup.

        Auto-dismisses after 8 seconds so the user has time to read a long
        passphrase.  A manual ✕ close button is also provided.
        """
        if not self._current_password:
            return

        # Close any existing popup first
        if self._password_popup:
            self._password_popup.destroy()

        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        popup.configure(bg=BG_ROW)
        top = self.winfo_toplevel()
        try:
            popup.transient(top)
        except tk.TclError:
            pass
        self._password_popup = popup

        # Position near cursor, nudged so it doesn't sit under the pointer
        popup.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")

        # Outer border frame
        frame = tk.Frame(popup, bg=BORDER, padx=1, pady=1)
        frame.pack(fill="both", expand=True)

        inner = tk.Frame(frame, bg=BG_ROW, padx=14, pady=10)
        inner.pack(fill="both", expand=True)

        # Title row with manual close button
        title_row = tk.Frame(inner, bg=BG_ROW)
        title_row.pack(fill="x")
        tk.Label(title_row, text="Saved password",
                 font=(FONT_BODY, 9), fg=TEXT_DIM, bg=BG_ROW).pack(side="left")
        close_btn = tk.Label(title_row, text="✕",
                             font=(FONT_BODY, 10), fg=TEXT_DIM, bg=BG_ROW,
                             cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self._hide_password_popup())

        # Password text
        tk.Label(inner, text=self._current_password,
                 font=(FONT_BODY, 12, "bold"),
                 fg=GREEN, bg=BG_ROW).pack(pady=(6, 4))

        # Copy button
        copy_btn = tk.Label(inner, text="📋  Copy to clipboard",
                            font=(FONT_BODY, 9),
                            fg=ACCENT, bg=BG_ROW, cursor="hand2")
        copy_btn.pack()
        copy_btn.bind("<Button-1>", lambda e: self._copy_password())

        popup.bind("<FocusOut>", lambda _e: self._hide_password_popup(), add="+")
        popup.bind("<Escape>", lambda _e: self._hide_password_popup(), add="+")
        for sequence in ("<Button-1>", "<Button-3>"):
            bind_id = top.bind(sequence, lambda _e: self._hide_password_popup(), add="+")
            if bind_id:
                self._password_popup_bind_ids.append((top, sequence, bind_id))

        # Auto-dismiss after 8 s — long enough to read a full passphrase
        popup.after(8_000, self._hide_password_popup)

    def _hide_password_popup(self):
        """Hide the password popup."""
        self._clear_password_popup_bindings()

        if self._password_popup:
            self._password_popup.destroy()
            self._password_popup = None

    def _add_detail_grid_row(self, parent: ctk.CTkFrame, label: str):
        """Create one label/value row in the details grid."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(
            row,
            text=label,
            font=ctk.CTkFont(FONT_BODY, 10),
            text_color=TEXT_DIM,
            width=100,
            anchor="w",
        ).pack(side="left")

        if label == "Password":
            self._password_label = tk.Label(
                row,
                text="",
                font=(FONT_BODY, 10, "bold"),
                fg=TEXT_DIM,
                bg=BG_CARD,
                anchor="w",
            )
            self._password_label.pack(side="left", padx=(8, 0))
            return

        lbl = SelectableText(
            row,
            font=(FONT_BODY, 10, "bold"),
            text_color=TEXT_MAIN,
            bg_color=BG_CARD,
            width=50,
            wrap="none",
        )
        lbl.pack(side="left", padx=(8, 0))
        self._value_labels[label] = lbl

    def _create_header_value(
        self,
        parent: ctk.CTkFrame,
        attr_name: str,
        *,
        font: tuple[str, int] | tuple[str, int, str],
        text_color: str,
        bg_color: str,
        width: int,
        wrap: Literal["none", "char", "word"] = "none",
        min_lines: int = 1,
        max_lines: int = 4,
        auto_height: bool = False,
        pady: tuple[int, int] | None = None,
        fill_x: bool = False,
    ) -> SelectableText:
        """Create and pack a header SelectableText field, storing it on *self*."""
        value = SelectableText(
            parent,
            font=font,
            text_color=text_color,
            bg_color=bg_color,
            width=width,
            wrap=wrap,
            min_lines=min_lines,
            max_lines=max_lines,
            auto_height=auto_height,
        )
        pack_kwargs: dict[str, Any] = {"anchor": "w"}
        if fill_x:
            pack_kwargs["fill"] = "x"
        if pady is not None:
            pack_kwargs["pady"] = pady
        value.pack(**pack_kwargs)
        setattr(self, attr_name, value)
        return value

    def _build_skeleton(self):
        """Build the fixed widget structure once; _populate() fills the data."""
        scroll_container = ctk.CTkFrame(self, fg_color="transparent")
        scroll_container.pack(fill="both", expand=True, padx=0, pady=0)
        scroll_container.grid_rowconfigure(0, weight=1)
        scroll_container.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(scroll_container, bg=BG_CARD, highlightthickness=0)
        v_scroll = ctk.CTkScrollbar(
            scroll_container,
            orientation="vertical",
            command=canvas.yview,
            button_color=BORDER,
            button_hover_color=ACCENT,
        )
        h_scroll = ctk.CTkScrollbar(
            scroll_container,
            orientation="horizontal",
            command=canvas.xview,
            button_color=BORDER,
            button_hover_color=ACCENT,
        )

        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        content = ctk.CTkFrame(canvas, fg_color="transparent")
        canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")
        self._detail_canvas = canvas
        self._detail_content = content
        self._detail_canvas_window = canvas_window

        content.bind("<Configure>", self._on_detail_content_configure)
        canvas.bind("<Configure>", self._on_detail_canvas_configure)

        # Header
        hdr = ctk.CTkFrame(content, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(20, 8))

        self._create_header_value(
            hdr,
            "_lbl_ssid",
            font=(FONT_TITLE, 22, "bold"),
            text_color=ACCENT,
            bg_color=BG_CARD,
            width=1,
            wrap="word",
            min_lines=1,
            max_lines=3,
            auto_height=True,
            fill_x=True,
        )

        self._create_header_value(
            hdr,
            "_lbl_connection_state",
            font=(FONT_BODY, 10, "bold"),
            text_color=TEXT_DIM,
            bg_color=BG_CARD,
            width=22,
            pady=(2, 0),
        )

        for attr_name, width in (
            ("_lbl_bssid", 44),
            ("_lbl_ipv4", 26),
            ("_lbl_ipv6", 44),
            ("_lbl_dns4", 44),
            ("_lbl_dns6", 44),
        ):
            self._create_header_value(
                hdr,
                attr_name,
                font=(FONT_BODY, 10),
                text_color=TEXT_DIM,
                bg_color=BG_CARD,
                width=width,
            )

        # Public IP toggle row
        pip_row = ctk.CTkFrame(hdr, fg_color="transparent")
        pip_row.pack(anchor="w", pady=(6, 0))
        ctk.CTkSwitch(
            pip_row, variable=self._public_ip_var, text="",
            onvalue=True, offvalue=False, width=40,
            progress_color=ACCENT, button_color=TEXT_MAIN,
            command=self._on_public_ip_toggle,
        ).pack(side="left")
        ctk.CTkLabel(
            pip_row, text="Show Public IP",
            font=ctk.CTkFont(FONT_BODY, 10),
            text_color=TEXT_DIM,
        ).pack(side="left", padx=(6, 0))

        self._create_header_value(
            hdr,
            "_lbl_public_ip",
            font=(FONT_BODY, 10),
            text_color=TEXT_DIM,
            bg_color=BG_CARD,
            width=26,
        )

        self._create_header_value(
            hdr,
            "_lbl_vendor_db",
            font=(FONT_BODY, 10, "bold"),
            text_color=TEXT_MAIN,
            bg_color=BG_CARD,
            width=34,
            min_lines=2,
            max_lines=4,
            auto_height=True,
            pady=(2, 0),
        )

        # Signal meter
        sig_frame = ctk.CTkFrame(content, fg_color=BG_ROW, corner_radius=8)
        sig_frame.pack(fill="x", padx=20, pady=8)

        sig_top = ctk.CTkFrame(sig_frame, fg_color="transparent")
        sig_top.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(sig_top, text="Signal Strength",
                     font=ctk.CTkFont(FONT_BODY, 10),
                     text_color=TEXT_DIM).pack(side="left")
        self._lbl_signal_val = SelectableText(
            sig_top,
            font=(FONT_BODY, 10, "bold"),
            text_color=TEXT_MAIN,
            bg_color=BG_ROW,
            width=18,
            wrap="none",
        )
        self._lbl_signal_val.pack(side="right")

        bar_bg = ctk.CTkFrame(sig_frame, fg_color=BORDER, height=6, corner_radius=3)
        bar_bg.pack(fill="x", padx=14, pady=(0, 4))
        bar_bg.pack_propagate(False)
        bar_fill = ctk.CTkFrame(
            bar_bg, fg_color=GREEN, height=6, width=4, corner_radius=3
        )
        bar_fill.place(x=0, y=0)
        self._bar_bg = bar_bg
        self._bar_fill = bar_fill

        self._lbl_quality = SelectableText(
            sig_frame,
            font=(FONT_BODY, 10),
            text_color=TEXT_MAIN,
            bg_color=BG_ROW,
            width=24,
            wrap="none",
        )
        self._lbl_quality.pack(pady=(0, 10))

        # Signal history chart
        hist_frame = ctk.CTkFrame(content, fg_color=BG_ROW, corner_radius=8)
        hist_frame.pack(fill="x", padx=20, pady=(0, 8))

        hist_top = ctk.CTkFrame(hist_frame, fg_color="transparent")
        hist_top.pack(fill="x", padx=14, pady=(8, 2))
        ctk.CTkLabel(
            hist_top, text="Signal History",
            font=ctk.CTkFont(FONT_BODY, 10),
            text_color=TEXT_DIM,
        ).pack(side="left")
        self._lbl_hist_count = ctk.CTkLabel(
            hist_top, text="",
            font=ctk.CTkFont(FONT_BODY, 9),
            text_color=TEXT_DIM,
        )
        self._lbl_hist_count.pack(side="right")

        self._signal_chart = SignalHistoryChart(hist_frame)
        self._signal_chart.pack(fill="x", padx=4, pady=(0, 8))

        # Details grid
        grid_frame = ctk.CTkFrame(content, fg_color="transparent")
        grid_frame.pack(fill="x", padx=20, pady=4)

        for label in [
            "Frequency", "Band", "Channel", "Bandwidth", "Max Rate",
            "Est. Speed", "Mode", "Security", "Encryption", "Password",
            "Vendor", "Congestion", "Quality", "Device", "Last Seen",
        ]:
            self._add_detail_grid_row(grid_frame, label)

        # Bind scroll gestures now that all children exist.
        bind_mousewheel_scrolling(content, self.scroll_from_event)
        bind_mousewheel_scrolling(canvas, self.scroll_from_event)

    def _on_detail_content_configure(self, _event):
        """Keep canvas scrollregion in sync with content size."""
        self._detail_canvas.configure(scrollregion=self._detail_canvas.bbox("all"))

    def _on_detail_canvas_configure(self, event):
        """Resize embedded content width to match or exceed canvas viewport."""
        target_width = max(event.width, self._detail_content.winfo_reqwidth())
        self._detail_canvas.itemconfigure(self._detail_canvas_window, width=target_width)
        if self._current_net is not None:
            self.after_idle(self._refresh_header_layout)
            self.after_idle(self._refresh_signal_meter)

    def _refresh_signal_meter(self):
        """Recompute signal bar fill against the current track width."""
        if self._current_net is None:
            return
        self._update_signal_meter(self._current_net.signal, self._current_net.quality_color)

    def _update_signal_meter(self, signal: int, color: str):
        """Update signal value text and bar fill using live geometry width."""
        track_width = self._bar_bg.winfo_width()
        if track_width <= 1:
            track_width = self._bar_bg.winfo_reqwidth()
        fill_width = int((signal / 100) * track_width)
        if signal > 0:
            fill_width = max(4, fill_width)
        fill_width = max(0, min(track_width, fill_width))
        self._bar_fill.configure(fg_color=color, width=fill_width)

    def _refresh_header_layout(self):
        """Recompute auto-height header fields after geometry updates."""
        if self._current_net is None:
            return
        for field in (
            self._lbl_ssid,
            self._lbl_bssid,
            self._lbl_ipv4,
            self._lbl_ipv6,
            self._lbl_dns4,
            self._lbl_dns6,
            self._lbl_vendor_db,
        ):
            field._adjust_height()

    def scroll_from_event(self, event):
        """Scroll detail content from a routed wheel/gesture event."""
        if event.num == 4:
            self._detail_canvas.yview_scroll(-1, "units")
            return "break"
        if event.num == 5:
            self._detail_canvas.yview_scroll(1, "units")
            return "break"

        delta = getattr(event, "delta", 0)
        if delta > 0:
            self._detail_canvas.yview_scroll(-1, "units")
            return "break"
        if delta < 0:
            self._detail_canvas.yview_scroll(1, "units")
            return "break"
        return None

    def _populate(self, net: WifiNetwork):
        """Update all stored label references with current network data."""
        self._current_net = net
        self._current_net_bssid = net.bssid

        # Header
        self._lbl_ssid.set_value(
            net.ssid,
            GREEN if net.in_use else ACCENT,
        )
        self._lbl_connection_state.set_value(
            "Status: Connected" if net.in_use else "Status: Not connected",
            GREEN if net.in_use else TEXT_DIM,
        )
        self._lbl_bssid.set_value(f"BSSID/MAC Address: {net.bssid}", TEXT_DIM)
        self._lbl_ipv4.set_value("IPv4: Fetching…" if net.in_use else "IPv4: —", TEXT_DIM)
        self._lbl_ipv6.set_value("IPv6: Fetching…" if net.in_use else "IPv6: —", TEXT_DIM)
        self._lbl_dns4.set_value("DNS4: Fetching…" if net.in_use else "DNS4: —", TEXT_DIM)
        self._lbl_dns6.set_value("DNS6: Fetching…" if net.in_use else "DNS6: —", TEXT_DIM)
        if net.in_use and self._public_ip_var.get():
            self._lbl_public_ip.set_value("Public IP: Fetching…", TEXT_DIM)
        elif net.in_use:
            self._lbl_public_ip.set_value("Public IP: —", TEXT_DIM)
        else:
            self._lbl_public_ip.set_value("Public IP: N/A", TEXT_DIM)
        manuf_path = system_manuf_path()
        if is_system_manuf_loaded() and manuf_path:
            self._lbl_vendor_db.set_value(
                f"Vendor DB:\n{manuf_path}",
                GREEN,
            )
        else:
            self._lbl_vendor_db.set_value(
                "Vendor DB:\nunavailable (install wireshark-common or ieee-data)",
                RED_COL,
            )

        # Signal meter
        self._lbl_signal_val.set_value(
            f"{net.signal}% · {net.signal_dbm}",
            net.quality_color,
        )
        self._update_signal_meter(net.signal, net.quality_color)
        self._lbl_quality.set_value(
            f"{net.quality_label}  ·  {net.bars}",
            net.quality_color,
        )

        # Computed colors
        congestion_color = RED_COL if net.congestion > 5 else YELLOW if net.congestion > 3 else GREEN
        encryption_color = (GREEN if "WPA3" in net.encryption_type or "WPA2" in net.encryption_type
                            else YELLOW if "WPA" in net.encryption_type else RED_COL)
        quality_color    = (GREEN if net.quality_score >= 70
                            else YELLOW if net.quality_score >= 40 else RED_COL)

        # Details grid
        updates = {
            "Frequency":  (net.frequency,                                                   TEXT_MAIN),
            "Band":       (net.band,                                                        TEXT_MAIN),
            "Channel":    (net.channel,                                                     TEXT_MAIN),
            "Bandwidth":  (net.bandwidth or "20 MHz",                                       TEXT_MAIN),
            "Max Rate":   (net.rate,                                                        TEXT_MAIN),
            "Est. Speed": (net.theoretical_max_speed,                                       TEXT_MAIN),
            "Mode":       (net.mode,                                                        TEXT_MAIN),
            "Security":   (net.security or "Open",                                          TEXT_MAIN),
            "Encryption": (net.encryption_type,                                             encryption_color),
            "Vendor":     (net.vendor.strip(),                                              TEXT_MAIN),
            "Congestion": (f"{net.congestion} network{'s' if net.congestion != 1 else ''}", congestion_color),
            "Quality":    (f"{net.quality_score}/100",                                      quality_color),
            "Device":     (net.device or "N/A",                                             TEXT_MAIN),
            "Last Seen":  (net.last_seen_str,                                               TEXT_MAIN),
        }
        for key, (text, color) in updates.items():
            self._value_labels[key].set_value(text, color)

        # Password row — reset to pending and kick off async fetch
        self._current_password = ""
        self._password_label.configure(text="Checking…", fg=TEXT_DIM, cursor="")
        self._password_label.unbind("<Button-1>")
        threading.Thread(
            target=self._fetch_password_async,
            args=(net.ssid, net.bssid),
            daemon=True
        ).start()

        # IPv4/IPv6 header labels — fetch async only when connected
        if net.in_use and net.device:
            threading.Thread(
                target=self._fetch_ip_async,
                args=(net.device, net.bssid),
                daemon=True,
            ).start()

        # Public IP — fetch async only when connected and toggle is on
        if net.in_use and self._public_ip_var.get():
            threading.Thread(
                target=self._fetch_public_ip_async,
                args=(net.bssid,),
                daemon=True,
            ).start()

    def update_signal_history(self, data: list[tuple[float, int]]) -> None:
        """Update the signal history chart. *data* is a list of (timestamp, signal%) pairs."""
        self._signal_chart.set_data(data)
        n = len(data)
        self._lbl_hist_count.configure(
            text=f"{n} sample{'s' if n != 1 else ''}" if n else ""
        )

    def show(self, net: WifiNetwork):
        """Display details for the selected network and hide placeholder."""
        self._reset_transient()
        self._populate(net)
        self._placeholder.place_forget()
        self.after_idle(self._refresh_header_layout)

    def _on_public_ip_toggle(self):
        """Called when the Public IP switch is toggled."""
        net = self._current_net
        if net is None:
            return
        if self._public_ip_var.get() and net.in_use:
            self._lbl_public_ip.set_value("Public IP: Fetching…", TEXT_DIM)
            threading.Thread(
                target=self._fetch_public_ip_async,
                args=(net.bssid,),
                daemon=True,
            ).start()
        else:
            self._lbl_public_ip.set_value(
                "Public IP: N/A" if not net.in_use else "Public IP: —", TEXT_DIM
            )

    def _fetch_public_ip_async(self, bssid: str):
        """Fetch the public IP off the main thread, then update the label."""
        ip = get_public_ip()
        self.after(0, self._update_public_ip_label, bssid, ip)

    def _update_public_ip_label(self, bssid: str, ip: str):
        """Called on the main thread once the public IP lookup completes."""
        if self._current_net_bssid != bssid:
            return
        self._lbl_public_ip.set_value(
            f"Public IP: {ip}" if ip else "Public IP: Unavailable",
            TEXT_MAIN if ip else TEXT_DIM,
        )

    def _fetch_ip_async(self, device: str, bssid: str):
        """Fetch adapter IP addresses and DNS off the main thread, then update the header labels."""
        ipv4, ipv6 = get_device_ips(device)
        dns4, dns6 = get_device_dns(device)
        self.after(0, self._update_ip_labels, bssid, ipv4, ipv6, dns4, dns6)

    def _update_ip_labels(self, bssid: str, ipv4: str, ipv6: str, dns4: str, dns6: str):
        """Called on the main thread once the IP/DNS lookup completes."""
        if self._current_net_bssid != bssid:
            return
        self._lbl_ipv4.set_value(f"IPv4: {ipv4 or '—'}", TEXT_MAIN if ipv4 else TEXT_DIM)
        self._lbl_ipv6.set_value(f"IPv6: {ipv6 or '—'}", TEXT_MAIN if ipv6 else TEXT_DIM)
        self._lbl_dns4.set_value(f"DNS4: {dns4 or '—'}", TEXT_MAIN if dns4 else TEXT_DIM)
        self._lbl_dns6.set_value(f"DNS6: {dns6 or '—'}", TEXT_MAIN if dns6 else TEXT_DIM)

    def _fetch_password_async(self, ssid: str, bssid: str):
        """Fetch saved password off the main thread, then update the label."""
        password = get_saved_password(ssid)
        # Schedule the UI update back on the main thread via after()
        self.after(0, self._update_password_label, bssid, password)

    def _update_password_label(self, bssid: str, password: str):
        """Called on the main thread once the password lookup completes."""
        # Bail out if the user has already selected a different network
        if self._current_net_bssid != bssid:
            return
        if not self._password_label.winfo_exists():
            return

        self._password_resolved = True
        if password:
            self._current_password = password
            masked_text = "●" * min(len(password), 12)
            self._password_label.configure(
                text=masked_text, fg=GREEN, cursor="hand2"
            )
            self._password_label.bind("<Button-1>", self._show_password_popup)
        else:
            self._password_label.configure(text="Not saved", fg=TEXT_DIM, cursor="")

    def get_cached_password(self, bssid: str) -> str | None:
        """Return the resolved saved password for *bssid*, or None if the
        lookup has not completed yet or *bssid* does not match the currently
        displayed network.  An empty string means the lookup finished and
        no saved password exists.
        """
        if not self._password_resolved or self._current_net_bssid != bssid:
            return None
        return self._current_password


# Stats panel

class StatsPanel(ctk.CTkFrame):
    """Statistics and channel-histogram panel shown above the network list."""

    def __init__(
        self,
        parent,
        *,
        on_adapter_info: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize a fixed-height panel used for summary and histogram."""
        super().__init__(parent, fg_color=BG_CARD, corner_radius=8,
                         height=STATS_HEIGHT, **kwargs)
        self._on_adapter_info = on_adapter_info
        self.pack_propagate(False)
        self.grid_propagate(False)

    def refresh(self, networks: list[WifiNetwork]) -> None:
        """Re-render the panel contents with updated *networks* data."""
        for w in self.winfo_children():
            w.destroy()

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=16, pady=6)

        # Left: Summary stats
        left = ctk.CTkFrame(container, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        stats_row = ctk.CTkFrame(left, fg_color="transparent")
        stats_row.pack(anchor="w", padx=(4, 0), expand=True)

        total = len(networks)
        band_counts = Counter(n.band for n in networks)
        band_24 = band_counts.get("2.4 GHz", 0)
        band_5 = band_counts.get("5 GHz", 0)
        band_6 = band_counts.get("6 GHz", 0)
        secured = sum(1 for n in networks if "WPA" in n.security)
        open_nets = total - secured

        def stat_label(label: str, value: int, color: str = TEXT_MAIN) -> None:
            f = ctk.CTkFrame(stats_row, fg_color="transparent")
            f.pack(side="left", padx=(0, 20))
            ctk.CTkLabel(f, text=label, font=_fira_font(12),
                         text_color=TEXT_DIM).pack()
            ctk.CTkLabel(f, text=str(value), font=_fira_font(24, "bold"),
                         text_color=color).pack()

        stat_label("Total", total, ACCENT)
        stat_label("2.4 GHz", band_24, YELLOW)
        stat_label("5 GHz", band_5, ACCENT)
        if band_6 > 0:
            stat_label("6 GHz", band_6, COLOR_6GHZ)
        stat_label("Secured", secured, GREEN)
        if open_nets > 0:
            stat_label("Open", open_nets, RED_COL)

        if self._on_adapter_info is not None:
            adapter_btn = ctk.CTkButton(
                self,
                text="🖧  Adapter",
                font=_fira_font(15, "bold"),
                width=120,
                height=30,
                fg_color=BG_ROW,
                text_color=ACCENT,
                hover_color=BG_HOVER,
                border_width=1,
                border_color=BORDER,
                corner_radius=6,
                command=self._on_adapter_info,
                 anchor="s",
            )
            adapter_btn.place(relx=0.5, y=12, anchor="n")

        # Right: Channel histogram
        right = ctk.CTkFrame(container, fg_color="transparent", width=350)
        right.pack(side="right", fill="both")

        hist_canvas = tk.Canvas(right, bg=BG_CARD, height=100, highlightthickness=0)
        hist_canvas.pack(fill="x", pady=(0, 0))

        separator_x = 150
        hist_canvas.create_text(
            separator_x,
            8,
            text="Channel Distribution",
            fill=TEXT_DIM,
            font=(FONT_BODY, 11),
            anchor="n",
        )

        channel_counts = Counter(n.channel for n in networks)
        channels_24 = {n.channel for n in networks if n.band == "2.4 GHz"}
        channels_5 = {n.channel for n in networks if n.band == "5 GHz"}
        if channel_counts:
            max_count = max(channel_counts.values())

            bar_width = 22
            gap = 8

            band_24_start = 10
            band_5_start = 200

            # Band labels: top at y=26, 9pt font ~12px tall → bottom ≈ y=38
            # Bar top: baseline_y(72) - max_bar_height(30) = 42 → 4px gap above bars
            # Bar bottom: y=72 → channel labels at y=80 (center) → 8px gap below bars
            if channels_24:
                hist_canvas.create_text(band_24_start, 26, text="2.4 GHz",
                                        fill=TEXT_DIM, font=(FONT_BODY, 9, "bold"),
                                        anchor="nw")

            if channels_5:
                hist_canvas.create_text(band_5_start, 26, text="5 GHz",
                                        fill=TEXT_DIM, font=(FONT_BODY, 9, "bold"),
                                        anchor="nw")

            if channels_24 and channels_5:
                hist_canvas.create_line(separator_x, 38, separator_x, 90,
                                        fill=TEXT_DIM, dash=(2, 2), width=1)

            if channels_24:
                self._draw_channel_bars(
                    canvas=hist_canvas,
                    channels=channels_24,
                    channel_counts=channel_counts,
                    max_count=max_count,
                    x_start=band_24_start,
                    bar_width=bar_width,
                    gap=gap,
                    label_font_size=10,
                    baseline_y=72,
                    label_y=84,
                    max_bar_height=30,
                )

            if channels_5:
                self._draw_channel_bars(
                    canvas=hist_canvas,
                    channels=channels_5,
                    channel_counts=channel_counts,
                    max_count=max_count,
                    x_start=band_5_start,
                    bar_width=bar_width,
                    gap=gap,
                    label_font_size=9,
                    baseline_y=72,
                    label_y=84,
                    max_bar_height=30,
                )

    def _draw_channel_bars(
        self,
        *,
        canvas: tk.Canvas,
        channels: set[str],
        channel_counts: Counter[str],
        max_count: int,
        x_start: int,
        bar_width: int,
        gap: int,
        label_font_size: int,
        baseline_y: int,
        label_y: int,
        max_bar_height: int,
    ) -> None:
        """Draw histogram bars for a channel set within one band segment."""
        x_offset = x_start
        for ch in sorted(int(c) for c in channels if c.isdigit()):
            ch_str = str(ch)
            count = channel_counts.get(ch_str, 0)
            if count <= 0:
                continue

            height = max(8, int((count / max_count) * max_bar_height))
            y1 = baseline_y - height
            color = RED_COL if count > 5 else YELLOW if count > 3 else GREEN
            canvas.create_rectangle(
                x_offset,
                y1,
                x_offset + bar_width,
                baseline_y,
                fill=color,
                outline="",
            )
            canvas.create_text(
                x_offset + bar_width // 2,
                label_y,
                text=ch_str,
                fill=TEXT_DIM,
                font=(FONT_BODY, label_font_size),
            )
            x_offset += bar_width + gap
