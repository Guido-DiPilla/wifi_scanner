"""Wi-Fi adapter information service."""

from __future__ import annotations

from typing import Any, TypedDict

from wifi_core.runner import CommandNotFoundError, CommandRunner, CommandTimeoutError


class AdapterInfo(TypedDict):
    """Structured snapshot of Wi-Fi adapter properties and capabilities."""

    device: str
    mac_address: str
    driver: str
    driver_version: str
    firmware_version: str
    supported_bands: list[str]
    supported_standards: list[str]
    tx_power: str
    regulatory_domain: str
    interface_mode: str
    phy: str
    capabilities: list[str]
    missing_tools: list[str]


_DEFAULT_RUNNER = CommandRunner()


def _safe_run_text(
    argv: list[str], timeout: int, runner: CommandRunner
) -> tuple[int, str, str]:
    """Run a command and return fallback empty output on tool/timeout errors."""
    try:
        result = runner.run(argv, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except (CommandNotFoundError, CommandTimeoutError):
        return 1, "", ""


def _detect_supported_bands(output: str) -> list[str]:
    """Infer supported RF bands from iw phy output."""
    bands: list[str] = []
    if any(freq in output for freq in ("2412", "2417", "2437")):
        bands.append("2.4 GHz")
    if any(freq in output for freq in ("5180", "5200", "5220", "5500", "5745")):
        bands.append("5 GHz")
    if any(freq in output for freq in ("5955", "6115", "6435")):
        bands.append("6 GHz")
    return bands


def _detect_supported_standards(output: str) -> list[str]:
    """Infer supported Wi-Fi standards from capability flags."""
    standards = set()
    if "HT20" in output or "HT40" in output:
        standards.add("802.11n (WiFi 4)")
    if "VHT" in output or "VHT80" in output or "VHT160" in output:
        standards.add("802.11ac (WiFi 5)")
    if "HE " in output or "HE PHY" in output or "HE MAC" in output:
        standards.add("802.11ax (WiFi 6)")
    if "EHT" in output:
        standards.add("802.11be (WiFi 7)")
    if standards:
        standards.add("802.11a/b/g")
    return sorted(list(standards), reverse=True)


def _detect_capabilities(output: str) -> list[str]:
    """Extract notable adapter features from iw capability text."""
    capabilities: list[str] = []
    if "MU-MIMO" in output or "SU Beamformee" in output:
        capabilities.append("MU-MIMO")
    if "Beamforming" in output or "beamformee" in output.lower() or "SU Beamformee" in output:
        capabilities.append("Beamforming")
    if "SAE" in output:
        capabilities.append("WPA3")
    if "HE PHY" in output:
        capabilities.append("OFDMA")
    if "VHT160" in output or "160 MHz" in output:
        capabilities.append("160 MHz channels")
    if "STBC" in output:
        capabilities.append("STBC")
    if "LDPC" in output:
        capabilities.append("LDPC")
    if "Dynamic channel bandwidth" in output:
        capabilities.append("Dynamic Bandwidth")
    return capabilities


def get_wifi_adapter_info(runner: CommandRunner | None = None) -> AdapterInfo:
    """Collect adapter identity, driver data, and wireless capabilities."""
    active_runner = runner or _DEFAULT_RUNNER
    info: AdapterInfo = {
        "device": "",
        "mac_address": "",
        "driver": "",
        "driver_version": "",
        "firmware_version": "",
        "supported_bands": [],
        "supported_standards": [],
        "tx_power": "",
        "regulatory_domain": "",
        "interface_mode": "",
        "phy": "",
        "capabilities": [],
        "missing_tools": [],
    }

    _, stdout, _ = _safe_run_text(["nmcli", "-t", "-f", "DEVICE,TYPE", "device"], 2, active_runner)
    for line in stdout.splitlines():
        if "wifi" in line.lower() and "p2p" not in line.lower():
            info["device"] = line.split(":")[0]
            break

    if not info["device"]:
        return info

    device = info["device"]

    try:
        mac_path = f"/sys/class/net/{device}/address"
        with open(mac_path, "r", encoding="utf-8") as f:
            info["mac_address"] = f.read().strip().upper()
    except (FileNotFoundError, PermissionError, OSError):
        pass

    try:
        uevent_path = f"/sys/class/net/{device}/device/uevent"
        with open(uevent_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DRIVER=") and not info["driver"]:
                    info["driver"] = line.split("=", 1)[1].strip()
    except (FileNotFoundError, PermissionError, OSError):
        pass

    ethtool_available = active_runner.command_exists("ethtool")
    if ethtool_available:
        _, stdout, _ = _safe_run_text(["ethtool", "-i", device], 2, active_runner)
        for line in stdout.splitlines():
            if line.startswith("driver:"):
                info["driver"] = line.split(":", 1)[1].strip()
            elif line.startswith("version:"):
                ver = line.split(":", 1)[1].strip()
                if ver:
                    info["driver_version"] = ver
            elif line.startswith("firmware-version:"):
                info["firmware_version"] = line.split(":", 1)[1].strip()
    else:
        info["missing_tools"].append("ethtool")

    iw_available = active_runner.command_exists("iw")
    if not iw_available:
        info["missing_tools"].append("iw")
        info["tx_power"] = "Install 'iw' tool"
        info["regulatory_domain"] = "Install 'iw' tool"
        info["interface_mode"] = "Install 'iw' tool"
        return info

    _, stdout, _ = _safe_run_text(["iw", "dev", device, "info"], 2, active_runner)
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("type "):
            info["interface_mode"] = line.split(" ", 1)[1]
        elif line.startswith("wiphy "):
            info["phy"] = line.split(" ", 1)[1]
        elif line.startswith("txpower "):
            info["tx_power"] = line.split(" ", 1)[1]

    _, stdout, _ = _safe_run_text(["iw", "reg", "get"], 2, active_runner)
    for line in stdout.splitlines():
        if line.startswith("country"):
            info["regulatory_domain"] = line.split(":", 1)[0].replace("country", "").strip()
            break
        if line.startswith("global"):
            info["regulatory_domain"] = "Global (00)"
            break

    if info["phy"]:
        _, output, _ = _safe_run_text(["iw", "phy", f"phy{info['phy']}", "info"], 3, active_runner)
        info["supported_bands"] = _detect_supported_bands(output)
        info["supported_standards"] = _detect_supported_standards(output)
        info["capabilities"] = _detect_capabilities(output)

    return info
