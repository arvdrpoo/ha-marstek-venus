"""Constants for the Marstek Venus E integration."""

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

# Platforms
PLATFORMS = ["sensor", "select", "binary_sensor"]
