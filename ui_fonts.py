"""Shared font factory functions for the Wi-Fi Scanner UI."""

from __future__ import annotations

from typing import Literal

import customtkinter as ctk

from config import FONT_BODY, FONT_TITLE


def fira_font(size: int, weight: Literal["normal", "bold"] | None = None) -> ctk.CTkFont:
    """Create a Fira Code CTkFont at the given size and optional weight."""
    if weight is None:
        return ctk.CTkFont(FONT_BODY, size)
    return ctk.CTkFont(FONT_BODY, size, weight)


def barlow_font(size: int, weight: Literal["normal", "bold"] = "bold") -> ctk.CTkFont:
    """Create a Barlow Condensed CTkFont at the given size and weight."""
    return ctk.CTkFont(FONT_TITLE, size, weight)
