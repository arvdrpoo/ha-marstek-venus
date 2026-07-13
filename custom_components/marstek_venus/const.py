"""Constants for the Marstek Venus E integration."""

from typing import Any, Optional

# Integration domain
DOMAIN = "marstek_venus"

# Configuration keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_ENABLE_WIFI_SENSORS = "enable_wifi_sensors"
CONF_ENABLE_BLE_SENSORS = "enable_ble_sensors"
CONF_ENABLE_PV_SENSORS = "enable_pv_sensors"

# Defaults
DEFAULT_NAME = "Marstek Venus E"
DEFAULT_PORT = 30000
DEFAULT_SCAN_INTERVAL = 30  # seconds
TIMEOUT = 10  # seconds for UDP response timeout
DEFAULT_ENABLE_WIFI_SENSORS = False  # WiFi sensors disabled by default
DEFAULT_ENABLE_BLE_SENSORS = False   # Bluetooth sensors disabled by default
DEFAULT_ENABLE_PV_SENSORS = False    # PV sensors (Venus D only)

# Validation ranges
MIN_SCAN_INTERVAL = 15   # seconds
MAX_SCAN_INTERVAL = 300  # 5 minutes
MIN_TIMEOUT = 5          # seconds
MAX_TIMEOUT = 30         # seconds

# Operating modes
MODE_AUTO = "Auto"
MODE_AI = "AI"
MODE_MANUAL = "Manual"
MODE_PASSIVE = "Passive"

# All supported modes for select entity
MODES = [MODE_AUTO, MODE_AI, MODE_MANUAL, MODE_PASSIVE]

# Lookup for normalizing raw ES.GetMode values to the canonical mode strings.
_MODE_BY_CASEFOLD = {mode.casefold(): mode for mode in MODES}


def normalize_mode(mode: Any) -> Optional[str]:
    """Map a raw ES.GetMode ``mode`` value to a canonical mode string.

    The Open API doc types ``mode`` as a number but documents and returns the
    strings Auto/AI/Manual/Passive. Match case-insensitively and tolerate
    surrounding whitespace so a firmware that reports e.g. ``"auto"`` still
    resolves. Returns None for anything unrecognised (including a numeric
    value, whose ordering the doc never defines) so callers show "unknown"
    rather than guessing a wrong mode.
    """
    if not isinstance(mode, str):
        return None
    return _MODE_BY_CASEFOLD.get(mode.strip().casefold())

# Passive-mode power control (charge/discharge setpoints)
# Upper bound for the charge/discharge Number entities, in watts. 2500 W is the
# Venus E continuous rating; bump if a larger unit is used. Manual/Passive on the
# wire is validated to +/-5000 W (see select.py), so this only caps the slider.
MAX_PASSIVE_POWER = 2500  # W
PASSIVE_POWER_STEP = 50   # W

# Repair issue key for a device that has stopped responding.
ISSUE_DEVICE_UNREACHABLE = "device_unreachable"

# Platforms
PLATFORMS = ["sensor", "select", "binary_sensor", "number"]
