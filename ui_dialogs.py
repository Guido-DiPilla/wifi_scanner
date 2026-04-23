"""
ui_dialogs.py — Standalone dialog factories for the Wi-Fi Scanner UI.

Each function creates and manages a modal CTkToplevel window.  They accept
the parent widget plus any data/callbacks they need, so they have no
dependency on WifiScannerApp internals.

Public API:
    show_adapter_info(parent)
    show_network_context_menu(parent, event, net, *, on_connect, on_disconnect, on_hidden_connect)
    show_password_dialog(parent, net, on_connect)
    show_error_dialog(parent, title, message)
    show_hidden_network_dialog(parent, on_connect)
"""
from __future__ import annotations

import threading
from typing import Callable, Literal

import customtkinter as ctk
import tkinter as tk

from config import (
    ACCENT,
    ACCENT_HOVER,
    BG_CARD,
    BG_DARK,
    BG_HOVER,
    BG_ROW,
    BORDER,
    FONT_BODY,
    GREEN,
    RED_COL,
    TEXT_DIM,
    TEXT_MAIN,
    YELLOW,
)
from ui_fonts import fira_font as _fira_font, barlow_font as _barlow_font
from ui_utils import enable_mousewheel_scrolling
from ui_widgets import SelectableText
from wifi_core.adapter_service import get_wifi_adapter_info
from wifi_core.models import WifiNetwork


# ── Adapter info ─────────────────────────────────────────────────────────────


def _center_dialog_on_parent(parent: ctk.CTk, dialog: ctk.CTkToplevel, width: int, height: int) -> None:
    dialog.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
    dialog.geometry(f"+{x}+{y}")


def _create_action_button(
    parent,
    *,
    text: str,
    command,
    primary: bool,
    width: int = 100,
):
    font = _fira_font(11, "bold" if primary else "normal")
    return ctk.CTkButton(
        parent,
        text=text,
        width=width,
        height=36,
        font=font,
        fg_color=ACCENT if primary else BG_ROW,
        text_color=BG_DARK if primary else TEXT_MAIN,
        hover_color=ACCENT_HOVER if primary else BG_HOVER,
        command=command,
    )

def _add_copyable_list(parent, title: str, items: list[str], color: str = TEXT_MAIN):
    """Render a titled list of items where each item is copyable."""
    ctk.CTkLabel(
        parent,
        text=title,
        font=_fira_font(14, "bold"),
        text_color=ACCENT,
        anchor="w"
    ).pack(fill="x", padx=15, pady=(15, 5))

    for item in items:
        item_widget = SelectableText(
            parent,
                font=(FONT_BODY, 11),
            text_color=color,
            bg_color=BG_CARD,
            width=35,
            wrap="word",
            min_lines=1,
            max_lines=2,
        )
        item_widget.pack(fill="x", padx=30, pady=2)
        item_widget.set_value(f"  • {item}")


def _add_info_section(parent, title: str, items: list[tuple[str, str]]):
    """Render a titled key-value section inside *parent* with copyable values."""
    ctk.CTkLabel(
        parent,
        text=title,
        font=_fira_font(14, "bold"),
        text_color=ACCENT,
        anchor="w"
    ).pack(fill="x", padx=15, pady=(15, 5))

    for label, value in items:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(
            row,
            text=f"{label}:",
            font=_fira_font(11),
            text_color=TEXT_DIM,
            width=150,
            anchor="w"
        ).pack(side="left", pady=2)

        # Use SelectableText for values so they're copyable (Ctrl+C, right-click)
        value_widget = SelectableText(
            row,
                font=(FONT_BODY, 11, "bold"),
            text_color=TEXT_MAIN,
            bg_color=BG_CARD,
            width=30,
            wrap="word",
            min_lines=1,
            max_lines=2,
        )
        value_widget.pack(side="left", padx=(10, 0), fill="both", expand=True)
        value_widget.set_value(value)


def show_adapter_info(parent: ctk.CTk) -> None:
    """Display WiFi adapter information in a modal dialog.

    The adapter query runs off the main thread so the dialog opens instantly
    without freezing the UI.
    """
    dialog = ctk.CTkToplevel(parent)
    dialog.title("WiFi Adapter Information")
    dialog.geometry("650x700")
    dialog.configure(fg_color=BG_DARK)
    dialog.transient(parent)

    # Title — shown immediately before data is available
    title_frame = ctk.CTkFrame(dialog, fg_color=BG_DARK)
    title_frame.pack(fill="x", padx=20, pady=(20, 10))
    ctk.CTkLabel(
        title_frame,
        text="WiFi Adapter Information",
        font=_barlow_font(28),
        text_color=ACCENT,
    ).pack(side="left")

    # Loading placeholder
    loading_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    loading_frame.pack(fill="both", expand=True)
    ctk.CTkLabel(
        loading_frame,
        text="Loading adapter information…",
        font=_fira_font(13),
        text_color=TEXT_DIM,
    ).pack(expand=True)

    def _load() -> None:
        info = get_wifi_adapter_info()
        dialog.after(0, lambda: _populate(info))

    def _populate(info) -> None:
        loading_frame.destroy()
        _build_adapter_content(dialog, info)

    threading.Thread(target=_load, daemon=True).start()


def _build_adapter_content(dialog: ctk.CTkToplevel, info) -> None:
    """Populate the adapter dialog with fetched info (called on the main thread)."""
    # Warning if tools are missing
    if info["missing_tools"]:
        warning_frame = ctk.CTkFrame(dialog, fg_color=BG_ROW, corner_radius=8)
        warning_frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            warning_frame,
            text="⚠ Missing Tools",
            font=_fira_font(12, "bold"),
            text_color=YELLOW,
            anchor="w"
        ).pack(fill="x", padx=15, pady=(10, 5))

        missing = ", ".join(info["missing_tools"])
        missing_text = SelectableText(
            warning_frame,
            font=(FONT_BODY, 10),
            text_color=TEXT_DIM,
            bg_color=BG_ROW,
            width=50,
            wrap="word",
            min_lines=1,
            max_lines=2,
        )
        missing_text.pack(fill="x", padx=15, pady=(0, 5))
        missing_text.set_value(f"Some features require: {missing}")

        install_cmd = f"sudo apt install {' '.join(info['missing_tools'])}"
        install_text = SelectableText(
            warning_frame,
            font=(FONT_BODY, 10),
            text_color=ACCENT,
            bg_color=BG_ROW,
            width=50,
            wrap="word",
            min_lines=1,
            max_lines=2,
        )
        install_text.pack(fill="x", padx=15, pady=(0, 10))
        install_text.set_value(f"Install with: {install_cmd}")

    # Scrollable content frame
    scroll_frame = ctk.CTkScrollableFrame(
        dialog,
        fg_color=BG_CARD,
        corner_radius=8
    )
    scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    # Device Information Section
    _add_info_section(scroll_frame, "DEVICE INFORMATION", [
        ("Device", info["device"] or "Not detected"),
        ("MAC Address", info["mac_address"] or "N/A"),
        ("Interface Mode", info["interface_mode"] or "N/A"),
        ("PHY", f"phy{info['phy']}" if info["phy"] else "N/A"),
    ])

    # Driver Information Section
    _add_info_section(scroll_frame, "DRIVER INFORMATION", [
        ("Driver", info["driver"] or "Unknown"),
        ("Driver Version", info["driver_version"] or "N/A"),
        ("Firmware Version", info["firmware_version"] or "N/A"),
    ])

    # Capabilities Section
    bands_str = ", ".join(info["supported_bands"]) if info["supported_bands"] else "Unknown"

    _add_info_section(scroll_frame, "CAPABILITIES", [
        ("Supported Bands", bands_str),
        ("Transmit Power", info["tx_power"] or "N/A"),
        ("Regulatory Domain", info["regulatory_domain"] or "Not set"),
    ])

    # Standards Section
    standards_list = info["supported_standards"] if info["supported_standards"] else ["Unknown"]
    _add_copyable_list(scroll_frame, "SUPPORTED STANDARDS", standards_list)

    # Features Section
    if info["capabilities"]:
        _add_copyable_list(scroll_frame, "ADVANCED FEATURES", info["capabilities"], GREEN)

    enable_mousewheel_scrolling(scroll_frame)

    # Close button
    _create_action_button(
        dialog,
        text="Close",
        command=dialog.destroy,
        primary=True,
        width=120,
    ).pack(pady=(0, 20))


# ── Password / connect dialog ─────────────────────────────────────────────────

def show_password_dialog(
    parent: ctk.CTk,
    net: WifiNetwork,
    on_connect: Callable[[str, str | None, str | None], None],
) -> None:
    """Show dialog to enter a WiFi password then invoke *on_connect(ssid, bssid, password)*."""
    dialog = ctk.CTkToplevel(parent)
    dialog.title(f"Connect to {net.ssid}")
    dialog.geometry("450x320")
    dialog.configure(fg_color=BG_DARK)
    dialog.transient(parent)
    dialog.grab_set()

    _center_dialog_on_parent(parent, dialog, width=450, height=320)

    # Content frame
    content = ctk.CTkFrame(dialog, fg_color=BG_CARD, corner_radius=12)
    content.pack(fill="both", expand=True, padx=20, pady=20)

    # Title
    ctk.CTkLabel(
        content,
        text=f"Connect to {net.ssid}",
        font=_fira_font(16, "bold"),
        text_color=ACCENT
    ).pack(pady=(20, 10))

    # Network info
    info_text = f"{net.security} · {net.band} · Channel {net.channel}"
    ctk.CTkLabel(
        content,
        text=info_text,
        font=_fira_font(10),
        text_color=TEXT_DIM
    ).pack(pady=(0, 20))

    # Password entry
    password_var = tk.StringVar()
    password_entry = ctk.CTkEntry(
        content,
        textvariable=password_var,
        placeholder_text="Enter password",
        width=350,
        height=40,
        font=_fira_font(12),
        fg_color=BG_DARK,
        border_color=BORDER,
        text_color=TEXT_MAIN,
        show="●"
    )
    password_entry.pack(pady=10)
    password_entry.focus()

    # Buttons
    btn_frame = ctk.CTkFrame(content, fg_color="transparent")
    btn_frame.pack(pady=20)

    def _on_connect():
        password = password_var.get().strip()
        if password:
            dialog.destroy()
            on_connect(net.ssid, net.bssid, password)

    def _on_cancel():
        dialog.destroy()

    _create_action_button(
        btn_frame,
        text="Cancel",
        command=_on_cancel,
        primary=False,
    ).pack(side="left", padx=10)

    _create_action_button(
        btn_frame,
        text="Connect",
        command=_on_connect,
        primary=True,
    ).pack(side="left", padx=10)

    password_entry.bind("<Return>", lambda e: _on_connect())
    dialog.bind("<Escape>", lambda e: _on_cancel())


# ── Error dialog ──────────────────────────────────────────────────────────────

def show_error_dialog(parent: ctk.CTk, title: str, message: str) -> None:
    """Show a read-only error dialog with *title* and *message*."""
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.geometry("500x280")
    dialog.configure(fg_color=BG_DARK)
    dialog.transient(parent)
    dialog.grab_set()

    _center_dialog_on_parent(parent, dialog, width=500, height=280)

    # Content frame
    content = ctk.CTkFrame(dialog, fg_color=BG_CARD, corner_radius=12)
    content.pack(fill="both", expand=True, padx=20, pady=20)

    # Title with error icon
    title_frame = ctk.CTkFrame(content, fg_color="transparent")
    title_frame.pack(pady=(20, 15))

    ctk.CTkLabel(
        title_frame,
        text="⚠",
        font=_fira_font(28),
        text_color=RED_COL
    ).pack(side="left", padx=(0, 10))

    ctk.CTkLabel(
        title_frame,
        text=title,
        font=_fira_font(16, "bold"),
        text_color=RED_COL
    ).pack(side="left")

    # Error message in scrollable text box
    message_frame = ctk.CTkFrame(content, fg_color=BG_DARK, corner_radius=8)
    message_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    message_text = ctk.CTkTextbox(
        message_frame,
        width=420,
        height=100,
        font=_fira_font(11),
        fg_color=BG_DARK,
        text_color=TEXT_MAIN,
        wrap="word"
    )
    message_text.pack(fill="both", expand=True, padx=2, pady=2)
    message_text.insert("1.0", message)
    message_text.configure(state="disabled")

    # OK button
    _create_action_button(
        content,
        text="OK",
        command=dialog.destroy,
        primary=True,
        width=120,
    ).pack(pady=(0, 20))

    dialog.bind("<Escape>", lambda e: dialog.destroy())
    dialog.bind("<Return>", lambda e: dialog.destroy())


# ── Hidden network dialog ─────────────────────────────────────────────────────

def show_hidden_network_dialog(
    parent: ctk.CTk,
    on_connect: Callable[[str, str | None, str | None], None],
) -> None:
    """Show dialog to connect to a hidden network.

    Invokes *on_connect(ssid, bssid, password)* where bssid is always None
    and password may be None for open networks.
    """
    dialog = ctk.CTkToplevel(parent)
    dialog.title("Connect to Hidden Network")
    dialog.geometry("450x300")
    dialog.configure(fg_color=BG_DARK)
    dialog.transient(parent)
    dialog.grab_set()

    _center_dialog_on_parent(parent, dialog, width=450, height=300)

    # Content frame
    content = ctk.CTkFrame(dialog, fg_color=BG_CARD, corner_radius=12)
    content.pack(fill="both", expand=True, padx=20, pady=20)

    # Title
    ctk.CTkLabel(
        content,
        text="Connect to Hidden Network",
        font=_fira_font(16, "bold"),
        text_color=ACCENT
    ).pack(pady=(20, 20))

    # SSID entry
    ctk.CTkLabel(
        content,
        text="Network Name (SSID)",
        font=_fira_font(10),
        text_color=TEXT_DIM,
        anchor="w"
    ).pack(pady=(0, 5), padx=50, fill="x")

    ssid_var = tk.StringVar()
    ssid_entry = ctk.CTkEntry(
        content,
        textvariable=ssid_var,
        placeholder_text="Enter SSID",
        width=350,
        height=40,
        font=_fira_font(12),
        fg_color=BG_DARK,
        border_color=BORDER,
        text_color=TEXT_MAIN
    )
    ssid_entry.pack(pady=(0, 15))
    ssid_entry.focus()

    # Password entry
    ctk.CTkLabel(
        content,
        text="Password (leave empty for open network)",
        font=_fira_font(10),
        text_color=TEXT_DIM,
        anchor="w"
    ).pack(pady=(0, 5), padx=50, fill="x")

    password_var = tk.StringVar()
    password_entry = ctk.CTkEntry(
        content,
        textvariable=password_var,
        placeholder_text="Enter password (optional)",
        width=350,
        height=40,
        font=_fira_font(12),
        fg_color=BG_DARK,
        border_color=BORDER,
        text_color=TEXT_MAIN,
        show="●"
    )
    password_entry.pack(pady=(0, 20))

    # Buttons
    btn_frame = ctk.CTkFrame(content, fg_color="transparent")
    btn_frame.pack(pady=10)

    def _on_connect():
        ssid = ssid_var.get().strip()
        if ssid:
            password = password_var.get().strip() or None
            dialog.destroy()
            on_connect(ssid, None, password)

    def _on_cancel():
        dialog.destroy()

    _create_action_button(
        btn_frame,
        text="Cancel",
        command=_on_cancel,
        primary=False,
    ).pack(side="left", padx=10)

    _create_action_button(
        btn_frame,
        text="Connect",
        command=_on_connect,
        primary=True,
    ).pack(side="left", padx=10)

    ssid_entry.bind("<Return>", lambda e: password_entry.focus())
    password_entry.bind("<Return>", lambda e: _on_connect())
    dialog.bind("<Escape>", lambda e: _on_cancel())


# ── Network context menu ─────────────────────────────────────────────────────

def show_network_context_menu(
    parent: tk.Misc,
    event,
    net: WifiNetwork,
    *,
    on_connect: Callable[[], None],
    on_disconnect: Callable[[], None],
    on_hidden_connect: Callable[[], None],
) -> Callable[[], None]:
    """Show a themed right-click context menu for *net*.

    Returns a no-arg dismiss callable so the caller can close the menu
    programmatically (e.g. when about to open a new one).
    """
    menu = tk.Toplevel(parent)
    menu.wm_overrideredirect(True)
    menu.configure(bg=BORDER)
    menu.transient(parent)
    menu.geometry(f"+{event.x_root}+{event.y_root}")

    border_frame = ctk.CTkFrame(menu, fg_color=BORDER, corner_radius=8)
    border_frame.pack(fill="both", expand=True)

    content = ctk.CTkFrame(border_frame, fg_color=BG_ROW, corner_radius=7)
    content.pack(fill="both", expand=True, padx=1, pady=1)

    bind_ids: list[tuple[str, str]] = []

    def dismiss() -> None:
        for sequence, bid in bind_ids:
            try:
                parent.unbind(sequence, bid)
            except tk.TclError:
                pass
        bind_ids.clear()
        try:
            menu.destroy()
        except tk.TclError:
            pass

    def run_action(action: Callable[[], None]) -> None:
        dismiss()
        parent.after(0, action)

    def add_item(
        text: str,
        *,
        action: Callable[[], None] | None = None,
        enabled: bool = True,
        color: str = TEXT_MAIN,
    ) -> None:
        row = ctk.CTkFrame(content, fg_color=BG_ROW, corner_radius=6)
        row.pack(fill="x", pady=1)
        label = ctk.CTkLabel(
            row,
            text=text,
            font=(FONT_BODY, 11),
            text_color=color,
            fg_color="transparent",
            padx=16,
            pady=8,
            anchor="w",
        )
        label.pack(fill="x")

        if enabled:
            row.configure(cursor="hand2")
            label.configure(cursor="hand2")

        if enabled and action is not None:
            def on_enter(_event):
                row.configure(fg_color=BG_HOVER)
                label.configure(text_color=ACCENT)

            def on_leave(_event):
                row.configure(fg_color=BG_ROW)
                label.configure(text_color=color)

            row.bind("<Enter>", on_enter)
            row.bind("<Leave>", on_leave)
            row.bind("<Button-1>", lambda _event: run_action(action))
            label.bind("<Button-1>", lambda _event: run_action(action))

    if net.in_use:
        add_item("✓ Connected", enabled=False, color=TEXT_DIM)
        ctk.CTkFrame(content, fg_color=BORDER, height=1, corner_radius=0).pack(fill="x", pady=2)
        add_item("Disconnect", action=on_disconnect)
    else:
        add_item("Connect", action=on_connect)

    ctk.CTkFrame(content, fg_color=BORDER, height=1, corner_radius=0).pack(fill="x", pady=2)
    add_item("Connect to Hidden Network...", action=on_hidden_connect)

    menu.bind("<FocusOut>", lambda _e: dismiss(), add="+")
    menu.bind("<Escape>", lambda _e: dismiss(), add="+")
    for sequence in ("<Button-1>", "<Button-3>"):
        bid = parent.bind(sequence, lambda _e: dismiss(), add="+")
        if bid:
            bind_ids.append((sequence, bid))

    try:
        menu.focus_force()
    except tk.TclError:
        pass

    return dismiss
