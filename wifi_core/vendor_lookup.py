"""Vendor lookup helpers for BSSID/OUI resolution."""

from __future__ import annotations

import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import NamedTuple


class PrefixEntry(NamedTuple):
    mask: int
    value: int
    vendor: str
    prefix_bits: int


_HEX_CHARS = set("0123456789ABCDEF")


_MANUF_PATHS: tuple[Path, ...] = (
    Path("/usr/share/wireshark/manuf"),
    Path("/usr/share/wireshark-common/manuf"),
    Path("/usr/lib/wireshark/manuf"),
)

_SYSTEM_IEEE_OUI_PATHS: tuple[Path, ...] = (
    Path("/usr/share/ieee-data/oui.txt"),
    Path("/usr/share/ieee-data/oui36.txt"),
    Path("/usr/share/ieee-data/mam.txt"),
    Path("/usr/share/ieee-data/iab.txt"),
    Path("/usr/share/misc/oui.txt"),
)

_CACHE_DIR = Path.home() / ".cache" / "wifi_scanner" / "ieee"

_IEEE_REMOTE_SOURCES: tuple[tuple[str, str], ...] = (
    ("oui.txt", "https://standards-oui.ieee.org/oui/oui.txt"),
    ("oui36.txt", "https://standards-oui.ieee.org/oui36/oui36.txt"),
    ("mam.txt", "https://standards-oui.ieee.org/mam/mam.txt"),
    ("iab.txt", "https://standards-oui.ieee.org/iab/iab.txt"),
)


def _normalize_oui(raw: str) -> str | None:
    cleaned = raw.strip().replace("-", ":").replace(".", "").upper()
    if len(cleaned) == 8 and cleaned.count(":") == 2:
        return cleaned
    if len(cleaned) == 6 and ":" not in cleaned:
        return f"{cleaned[0:2]}:{cleaned[2:4]}:{cleaned[4:6]}"
    return None


def _cache_ieee_paths() -> tuple[Path, ...]:
    return tuple(_CACHE_DIR / name for name, _url in _IEEE_REMOTE_SOURCES)


def _ieee_oui_paths() -> tuple[Path, ...]:
    cache_paths = tuple(path for path in _cache_ieee_paths() if path.exists())
    return cache_paths + _SYSTEM_IEEE_OUI_PATHS


def refresh_authoritative_ieee_cache(force: bool = False, timeout: float = 20.0) -> bool:
    """Download and cache authoritative IEEE registry files.

    Returns True when files were downloaded and updated, otherwise False.
    """
    cache_paths = _cache_ieee_paths()
    if not force and all(path.exists() for path in cache_paths):
        return False

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in _IEEE_REMOTE_SOURCES:
        dst = _CACHE_DIR / name
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                payload = response.read()
        except (OSError, urllib.error.URLError, TimeoutError):
            return False

        text = payload.decode("utf-8", errors="ignore")
        if "(hex)" not in text and "(base 16)" not in text:
            return False

        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=_CACHE_DIR) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)
        tmp_path.replace(dst)
    return True


def _parse_prefix_token(raw: str) -> tuple[int, int, int] | None:
    """Parse a Wireshark/IEEE prefix token into (value, mask, prefix_bits)."""
    token = raw.strip().upper()
    if not token:
        return None

    prefix_bits: int | None = None
    if "/" in token:
        base, bits_raw = token.split("/", 1)
        try:
            prefix_bits = int(bits_raw)
        except ValueError:
            return None
    else:
        base = token

    cleaned = "".join(ch for ch in base if ch in _HEX_CHARS)
    if not cleaned:
        return None

    available_bits = len(cleaned) * 4
    if prefix_bits is None:
        prefix_bits = available_bits

    if prefix_bits < 1 or prefix_bits > 48 or prefix_bits > available_bits:
        return None

    value = int(cleaned, 16) << (48 - available_bits)
    mask = ((1 << prefix_bits) - 1) << (48 - prefix_bits)
    return value & mask, mask, prefix_bits


def _parse_ieee_base16_range(raw: str, oui24_value: int | None) -> tuple[int, int, int] | None:
    """Parse IEEE range tokens like F2F000-F2FFFF using the current OUI24."""
    token = raw.strip().upper()
    if "-" not in token or oui24_value is None:
        return None

    start_raw, end_raw = token.split("-", 1)
    start = "".join(ch for ch in start_raw if ch in _HEX_CHARS)
    end = "".join(ch for ch in end_raw if ch in _HEX_CHARS)
    if not start or not end or len(start) != len(end):
        return None

    bits = len(start) * 4
    if bits != 24:
        return None

    try:
        start_val = int(start, 16)
        end_val = int(end, 16)
    except ValueError:
        return None
    if end_val < start_val:
        return None

    diff = start_val ^ end_val
    common_bits = 24 - diff.bit_length()
    if common_bits < 0:
        return None

    if common_bits == 0:
        low_prefix = 0
    else:
        low_prefix = start_val & ~((1 << (24 - common_bits)) - 1)

    prefix_bits = 24 + common_bits
    full_value = ((oui24_value & 0xFFFFFF) << 24) | (low_prefix & 0xFFFFFF)
    mask = ((1 << prefix_bits) - 1) << (48 - prefix_bits)
    return full_value & mask, mask, prefix_bits


def _mac_int_to_oui(mac_int: int) -> str:
    return f"{(mac_int >> 40) & 0xFF:02X}:{(mac_int >> 32) & 0xFF:02X}:{(mac_int >> 24) & 0xFF:02X}"


def _bssid_to_mac_int(bssid: str) -> int | None:
    cleaned = "".join(ch for ch in bssid.upper() if ch in _HEX_CHARS)
    if len(cleaned) < 12:
        return None
    try:
        return int(cleaned[:12], 16)
    except ValueError:
        return None


def _load_wireshark_manuf() -> tuple[dict[str, str], list[PrefixEntry], Path | None]:
    for path in _MANUF_PATHS:
        if path.exists():
            exact_db: dict[str, str] = {}
            prefix_db: list[PrefixEntry] = []
            try:
                with path.open(encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split("\t")
                        if len(parts) < 2:
                            parts = line.split()
                        if len(parts) < 2:
                            continue
                        parsed = _parse_prefix_token(parts[0])
                        if not parsed:
                            continue
                        value, mask, prefix_bits = parsed
                        vendor = parts[1].strip()
                        if not vendor:
                            continue
                        prefix_db.append(PrefixEntry(mask, value, vendor, prefix_bits))
                        if prefix_bits == 24:
                            exact_db[_mac_int_to_oui(value)] = vendor
            except OSError:
                pass

            if prefix_db:
                prefix_db.sort(key=lambda entry: entry.prefix_bits, reverse=True)
                return exact_db, prefix_db, path
    return {}, [], None


def _load_ieee_oui() -> tuple[dict[str, str], Path | None]:
    db: dict[str, str] = {}
    selected_path: Path | None = None
    for path in _ieee_oui_paths():
        if not path.exists():
            continue

        current_oui24: int | None = None
        try:
            with path.open(encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue

                    if "(hex)" in line:
                        prefix, vendor = line.split("(hex)", 1)
                        vendor = vendor.strip()
                        parsed = _parse_prefix_token(prefix)
                        if parsed and parsed[2] >= 24:
                            current_oui24 = (parsed[0] >> 24) & 0xFFFFFF
                        if parsed and parsed[2] == 24 and vendor:
                            db[_mac_int_to_oui(parsed[0])] = vendor
                            if selected_path is None:
                                selected_path = path
                        continue

                    if "(base 16)" not in line:
                        continue

                    prefix, vendor = line.split("(base 16)", 1)
                    vendor = vendor.strip()
                    if not vendor:
                        continue

                    parsed = _parse_prefix_token(prefix)
                    if parsed and parsed[2] == 24:
                        db[_mac_int_to_oui(parsed[0])] = vendor
                        if selected_path is None:
                            selected_path = path
                        continue

                    range_parsed = _parse_ieee_base16_range(prefix, current_oui24)
                    if range_parsed and range_parsed[2] == 24:
                        db[_mac_int_to_oui(range_parsed[0])] = vendor
                        if selected_path is None:
                            selected_path = path
        except OSError:
            pass

    return db, selected_path


def _load_system_oui_db() -> tuple[dict[str, str], list[PrefixEntry], Path | None]:
    wireshark_db, wireshark_prefixes, wireshark_path = _load_wireshark_manuf()
    if wireshark_db or wireshark_prefixes:
        return wireshark_db, wireshark_prefixes, wireshark_path

    ieee_db, ieee_path = _load_ieee_oui()
    ieee_prefixes: list[PrefixEntry] = []
    for oui, vendor in ieee_db.items():
        parsed = _parse_prefix_token(oui)
        if not parsed:
            continue
        value, mask, prefix_bits = parsed
        ieee_prefixes.append(PrefixEntry(mask, value, vendor, prefix_bits))
    ieee_prefixes.sort(key=lambda entry: entry.prefix_bits, reverse=True)
    return ieee_db, ieee_prefixes, ieee_path


def _reload_vendor_state() -> None:
    global _OUI_DB, _OUI_PREFIX_DB, _OUI_DB_PATH
    _OUI_DB, _OUI_PREFIX_DB, _OUI_DB_PATH = _load_system_oui_db()


def _best_prefix_vendor(mac_int: int) -> str | None:
    # _OUI_PREFIX_DB is sorted by prefix_bits descending, so the first match
    # is always the longest (most specific) prefix — return immediately.
    for entry in _OUI_PREFIX_DB:
        if (mac_int & entry.mask) == entry.value:
            return entry.vendor
    return None


_OUI_DB: dict[str, str]
_OUI_PREFIX_DB: list[PrefixEntry]
_OUI_DB_PATH: Path | None
_reload_vendor_state()


def reload_vendor_database(force_refresh: bool = False) -> bool:
    """Reload vendor database from source files.

    If force_refresh is True, first attempts to download authoritative IEEE files.
    Returns True when any vendor data is loaded after reload.
    """
    if force_refresh:
        refresh_authoritative_ieee_cache(force=True)

    _reload_vendor_state()
    return bool(_OUI_DB or _OUI_PREFIX_DB)


def is_system_manuf_loaded() -> bool:
    return bool(_OUI_DB or _OUI_PREFIX_DB)


def system_manuf_path() -> str | None:
    return str(_OUI_DB_PATH) if _OUI_DB_PATH else None


def get_vendor(bssid: str) -> str:
    mac_int = _bssid_to_mac_int(bssid)
    if mac_int is None:
        return "Unknown"

    exact = _OUI_DB.get(_mac_int_to_oui(mac_int))
    if exact:
        return exact

    return _best_prefix_vendor(mac_int) or "Unknown"
