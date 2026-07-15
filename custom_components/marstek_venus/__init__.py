"""The Marstek Venus E integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.storage import Store

from .api import MarstekApiClient, MarstekConnectionError
from .const import (
    CONF_AUTO_REASSERT,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_ENABLE_WIFI_SENSORS,
    CONF_ENABLE_BLE_SENSORS,
    CONF_ENABLE_PV_SENSORS,
    DEFAULT_AUTO_REASSERT,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_ENABLE_WIFI_SENSORS,
    DEFAULT_ENABLE_BLE_SENSORS,
    DEFAULT_ENABLE_PV_SENSORS,
    DOMAIN,
    SCHEDULE_STORAGE_KEY,
    SCHEDULE_STORAGE_VERSION,
    TIMEOUT,
)
from .coordinator import MarstekDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# List of platforms this integration provides
PLATFORMS = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.TIME,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up Marstek Venus E from a config entry.

    This function is called when the integration is loaded.
    It performs the following steps:
    1. Extract configuration (IP address, port)
    2. Create API client and connect to device
    3. Get initial device information
    4. Create data update coordinator
    5. Perform initial data fetch
    6. Store client and coordinator in hass.data
    7. Load platforms (sensor, select)

    Args:
        hass: Home Assistant instance
        entry: The config entry containing user configuration

    Returns:
        True if setup was successful

    Raises:
        ConfigEntryNotReady: If device is not reachable
    """
    # Extract configuration from the config entry
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    # Ensure options are set with defaults for existing installations
    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                CONF_TIMEOUT: TIMEOUT,
                CONF_ENABLE_WIFI_SENSORS: DEFAULT_ENABLE_WIFI_SENSORS,
                CONF_ENABLE_BLE_SENSORS: DEFAULT_ENABLE_BLE_SENSORS,
                CONF_ENABLE_PV_SENSORS: DEFAULT_ENABLE_PV_SENSORS,
                CONF_AUTO_REASSERT: DEFAULT_AUTO_REASSERT,
            }
        )

    # Get options (with fallback to defaults)
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = entry.options.get(CONF_TIMEOUT, TIMEOUT)
    enable_wifi = entry.options.get(CONF_ENABLE_WIFI_SENSORS, DEFAULT_ENABLE_WIFI_SENSORS)
    enable_ble = entry.options.get(CONF_ENABLE_BLE_SENSORS, DEFAULT_ENABLE_BLE_SENSORS)
    enable_pv = entry.options.get(CONF_ENABLE_PV_SENSORS, DEFAULT_ENABLE_PV_SENSORS)
    auto_reassert = entry.options.get(CONF_AUTO_REASSERT, DEFAULT_AUTO_REASSERT)

    # Load the HA-owned Manual schedule (source of truth; the device cannot
    # report its slot table back over the local API).
    schedule_store = Store(
        hass, SCHEDULE_STORAGE_VERSION, f"{SCHEDULE_STORAGE_KEY}.{entry.entry_id}"
    )
    stored_schedule = await schedule_store.async_load()

    _LOGGER.info("Setting up Marstek Venus E at %s:%s", host, port)

    # Create the API client
    client = MarstekApiClient(host, port, timeout)

    try:
        # Connect to the device
        await client.connect()

        # Config flow just validated the connection, so wait before our first call
        # (Rate limiting only works within a single client instance)
        await asyncio.sleep(2.5)

        # Get device information
        # This also validates that the device is reachable
        device_info = await client.get_device_info()
        _LOGGER.debug("Device info: %s", device_info)

    except (MarstekConnectionError, asyncio.TimeoutError, TimeoutError) as err:
        # Device is not reachable (offline, or its local API is toggled off).
        # Raise ConfigEntryNotReady so HA retries setup with backoff instead of
        # erroring out; the entry loads automatically once the device returns.
        await client.close()
        raise ConfigEntryNotReady(f"Unable to reach device: {err}") from err

    # Create the data update coordinator with custom scan interval
    coordinator = MarstekDataUpdateCoordinator(
        hass,
        client,
        device_info,
        entry.entry_id,
        scan_interval,
        enable_wifi=enable_wifi,
        enable_ble=enable_ble,
        enable_pv=enable_pv,
        schedule=stored_schedule,
        store=schedule_store,
        auto_reassert=auto_reassert,
    )

    # Fetch initial data
    # This ensures we have data before entities are created
    # Note: Rate limiting is handled automatically by the API client
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator and client in hass.data
    # This makes them accessible to the platforms (sensor, select)
    # Structure: hass.data[DOMAIN][entry_id] = {"coordinator": ..., "client": ...}
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "device_info": device_info,
    }

    # Forward entry setup to platforms
    # This will load sensor.py and select.py
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Marstek Venus E setup complete")
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry to the current version.

    v1 -> v2: normalise the unique ID to the MAC format produced by
    format_mac, so DHCP discovery (which only has the MAC) matches entries
    that were originally created from the device's raw wifi_mac. Entity
    unique IDs are left untouched, so no state history is lost.
    """
    if entry.version == 1:
        new_unique_id = (
            format_mac(entry.unique_id) if entry.unique_id else entry.unique_id
        )
        hass.config_entries.async_update_entry(
            entry, unique_id=new_unique_id, version=2
        )
        _LOGGER.info(
            "Migrated Marstek config entry to v2 (unique_id %s -> %s)",
            entry.unique_id,
            new_unique_id,
        )
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Unload a config entry.

    This function is called when the integration is being removed or reloaded.
    It should clean up all resources.

    Args:
        hass: Home Assistant instance
        entry: The config entry being unloaded

    Returns:
        True if unload was successful
    """
    _LOGGER.info("Unloading Marstek Venus E integration")

    # Unload platforms
    # This removes all entities
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Close the API client connection and remove stored data.
        # Guard against a partially-initialised entry (setup that failed
        # before storing its data).
        data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if data:
            client: MarstekApiClient = data["client"]
            await client.close()

    return unload_ok
