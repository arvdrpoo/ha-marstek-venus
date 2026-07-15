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
PLATFORMS = ["sensor", "select", "binary_sensor", "number", "switch", "time", "button"]

# --- HA-owned Manual schedule ------------------------------------------------
# The local API cannot READ the device's Manual slot table (ES.GetMode only
# returns the active mode + power; there is no get-schedule method). So HA is
# the source of truth for the schedule: it stores the slots, shows/edits them
# as per-slot entities, and writes them to the device with ES.SetMode.

# Number of Manual-schedule slots surfaced as HA entities. The device supports
# 10 (time_num 0-9); we expose a smaller, manageable set.
NUM_SCHEDULE_SLOTS = 4

# Day-of-week presets. Value is the device week_set bitmap: a byte, low 7 bits,
# bit 0 = Monday .. bit 6 = Sunday; 127 = every day.
DAY_PRESET_EVERYDAY = "everyday"
DAY_PRESET_WEEKDAYS = "weekdays"
DAY_PRESET_WEEKEND = "weekend"
DAY_PRESETS = {
    DAY_PRESET_EVERYDAY: 0b1111111,  # 127, Mon-Sun
    DAY_PRESET_WEEKDAYS: 0b0011111,  # 31,  Mon-Fri
    DAY_PRESET_WEEKEND: 0b1100000,   # 96,  Sat-Sun
}
DAY_PRESET_LABELS = {
    DAY_PRESET_EVERYDAY: "Every day",
    DAY_PRESET_WEEKDAYS: "Mon-Fri",
    DAY_PRESET_WEEKEND: "Sat-Sun",
}

# Bound for a schedule slot's power slider, in watts. Signed: negative = charge,
# positive = discharge (the device wire convention for manual_cfg.power).
MAX_MANUAL_POWER = 2500

# Passive-mode quick control (the repurposed Charge/Discharge number entities).
# Passive holds a power for a countdown, then the device reverts on its own, so
# these never touch the Manual slot table.
DEFAULT_PASSIVE_COUNTDOWN = 3600  # seconds a Passive setpoint holds
MIN_PASSIVE_COUNTDOWN = 60
MAX_PASSIVE_COUNTDOWN = 86400

# Auto re-assert the HA-owned schedule to the device after it recovers from an
# outage. Off by default: it forces the device into Manual mode on recovery,
# which is a surprising side effect to enable implicitly. Turn it on to make the
# schedule survive a device reset without a manual re-apply.
CONF_AUTO_REASSERT = "auto_reassert_schedule"
DEFAULT_AUTO_REASSERT = False

# Persistent store for the HA-owned schedule (keyed per config entry).
SCHEDULE_STORAGE_VERSION = 1
SCHEDULE_STORAGE_KEY = f"{DOMAIN}.schedule"
