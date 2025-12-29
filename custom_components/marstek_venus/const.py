"""Constants for the Marstek Venus E integration."""

# Integration domain
DOMAIN = "marstek_venus"

# Configuration keys
CONF_HOST = "host"
CONF_PORT = "port"

# Defaults
DEFAULT_NAME = "Marstek Venus E"
DEFAULT_PORT = 30000
DEFAULT_SCAN_INTERVAL = 30  # seconds
TIMEOUT = 10  # seconds for UDP response timeout

# Operating modes
MODE_AUTO = "Auto"
MODE_AI = "AI"
MODE_MANUAL = "Manual"
MODE_PASSIVE = "Passive"

# All supported modes for select entity
MODES = [MODE_AUTO, MODE_AI, MODE_MANUAL, MODE_PASSIVE]

# Platforms
PLATFORMS = ["sensor", "select"]
