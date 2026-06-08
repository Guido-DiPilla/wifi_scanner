# SPDX-License-Identifier: MIT
"""Reusable UI helpers for Wi-Fi Scanner."""

from __future__ import annotations

from typing import Callable

import tkinter as tk


def bind_mousewheel_scrolling(widget: tk.Misc, on_scroll: Callable[[tk.Event], str | None]) -> None:
    """Bind mouse wheel scrolling recursively for *widget* and all descendants."""

    def bind_recursive(current: tk.Misc) -> None:
        current.bind("<MouseWheel>", on_scroll, add="+")
        current.bind("<Button-4>", on_scroll, add="+")
        current.bind("<Button-5>", on_scroll, add="+")
        for child in current.winfo_children():
            bind_recursive(child)

    bind_recursive(widget)


def enable_mousewheel_scrolling(scroll_frame):
    """Enable wheel scrolling for a CTkScrollableFrame using its canvas if available."""

    canvas = getattr(scroll_frame, "_parent_canvas", None)
    if canvas is None:
        return

    def on_scroll(event):
        if getattr(event, "num", None) == 4:
            canvas.yview_scroll(-1, "units")
            return "break"
        if getattr(event, "num", None) == 5:
            canvas.yview_scroll(1, "units")
            return "break"

        delta = getattr(event, "delta", 0)
        if delta > 0:
            canvas.yview_scroll(-1, "units")
            return "break"
        if delta < 0:
            canvas.yview_scroll(1, "units")
            return "break"
        return None

    bind_mousewheel_scrolling(scroll_frame, on_scroll)
