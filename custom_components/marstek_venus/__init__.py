"""The Marstek Venus E integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import MarstekApiClient, MarstekConnectionError
from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN
from .coordinator import MarstekDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# List of platforms this integration provides
PLATFORMS = [Platform.SENSOR, Platform.SELECT]


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

    _LOGGER.info("Setting up Marstek Venus E at %s:%s", host, port)

    # Create the API client
    client = MarstekApiClient(host, port)

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

    except MarstekConnectionError as err:
        # Device is not reachable
        # Raise ConfigEntryNotReady to tell HA to retry later
        await client.close()
        raise ConfigEntryNotReady(f"Unable to connect to device: {err}") from err

    # Create the data update coordinator
    coordinator = MarstekDataUpdateCoordinator(hass, client, device_info)

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

    _LOGGER.info("Marstek Venus E setup complete")
    return True


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
        # Close the API client connection
        data = hass.data[DOMAIN][entry.entry_id]
        client: MarstekApiClient = data["client"]
        await client.close()

        # Remove stored data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
