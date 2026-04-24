"""Shared UI configuration for Wi-Fi Scanner."""

from pathlib import Path

__version__ = (Path(__file__).parent / "VERSION").read_text().strip()

# Font families (size and weight are specified at each usage site)
FONT_MONO = "JetBrains Mono"
FONT_BODY = "Fira Code"
FONT_TITLE = "Barlow Condensed"

# Colors
BG_DARK = "#0d1117"
BG_CARD = "#161b22"
BG_ROW = "#1c2128"
BG_HOVER = "#21262d"
ACCENT = "#58a6ff"
ACCENT2 = "#f78166"
ACCENT_HOVER = "#79b8ff"
FOCUS_RING = "#79c0ff"
COLOR_6GHZ = "#b39ddb"
ROW_SELECTED_BG = "#243b57"
ROW_SELECTED_IN_USE_BG = "#1a3452"
ROW_SELECTED_HOVER_BG = "#2d4a6b"
TEXT_DIM = "#8b949e"
TEXT_MAIN = "#e6edf3"
BORDER = "#30363d"
GREEN = "#00e676"
YELLOW = "#ffca28"
RED_COL = "#ef5350"

# Layout
TOPBAR_HEIGHT: int = 56
STATS_HEIGHT: int = 110
DETAIL_PANEL_WIDTH: int = 360
WINDOW_WIDTH: int = 1450
WINDOW_HEIGHT: int = 950
MIN_WINDOW_WIDTH: int = 1280

# Display limits
MAX_SSID_DISPLAY: int = 28
MAX_SECURITY_DISPLAY: int = 13

# Scanning intervals (seconds)
DEFAULT_SCAN_INTERVAL: int = 30
MIN_SCAN_INTERVAL: int = 1
MAX_SCAN_INTERVAL: int = 300

# Quality-scoring weights (used by WifiNetwork.quality_score)
SIGNAL_WEIGHT: float = 0.6
WPA3_BONUS: int = 20
WPA2_BONUS: int = 10
OPEN_PENALTY: int = 10
CONGESTION_THRESHOLD_LOW: int = 1    # congestion > this → mild penalty
CONGESTION_THRESHOLD_MED: int = 3    # congestion > this → medium penalty
CONGESTION_THRESHOLD_HIGH: int = 5   # congestion > this → heavy penalty
CONGESTION_PENALTY_LOW: int = 5
CONGESTION_PENALTY_MED: int = 10
CONGESTION_PENALTY_HIGH: int = 15
BANDWIDTH_BONUS_160: int = 20
BANDWIDTH_BONUS_80: int = 10
BANDWIDTH_BONUS_40: int = 5
THROUGHPUT_EFFICIENCY: float = 0.75
