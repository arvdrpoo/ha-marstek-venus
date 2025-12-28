"""Data update coordinator for Marstek Venus E."""
import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import MarstekApiClient, MarstekConnectionError, MarstekApiError
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MarstekDataUpdateCoordinator(DataUpdateCoordinator):
    """
    Class to manage fetching Marstek device data.

    The DataUpdateCoordinator is a Home Assistant helper that:
    - Polls the device at regular intervals
    - Handles errors and retries automatically
    - Provides data to all entities efficiently (they share the same data)
    - Marks entities as unavailable when updates fail

    All sensor and select entities use this coordinator to get their data,
    so we only need to poll the device once per update cycle.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: MarstekApiClient,
        device_info: Dict[str, Any],
    ) -> None:
        """
        Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            client: The API client for device communication
            device_info: Basic device information from initial connection
        """
        self.client = client
        self.device_info = device_info

        # Initialize the parent DataUpdateCoordinator
        # The name appears in debug logs
        super().__init__(
            hass,
            _LOGGER,
            name="Marstek Venus E",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """
        Fetch data from the device.

        This method is called automatically by Home Assistant at the
        configured update_interval. It should:
        1. Fetch all necessary data from the device
        2. Return a dictionary with all the data
        3. Raise UpdateFailed if something goes wrong

        Returns:
            Dictionary containing all device data:
            {
                "es": {...},      # Energy system data
                "bat": {...},     # Battery data (from Bat.GetStatus or ES.GetStatus)
                "mode": {...},    # Current operating mode
                "em": {...},      # Energy meter data (or None)
                "wifi": {...},    # WiFi status data (or None)
                "ble": {...},     # Bluetooth status data (or None)
                "pv": {...}       # PV (solar) status data (or None, Venus D only)
            }

        Raises:
            UpdateFailed: If data fetch fails
        """
        try:
            # Fetch data from API endpoints
            # Note: Venus E 3 only supports some endpoints, not all from the docs

            _LOGGER.debug("Fetching energy system status")
            es_data = await self.client.get_es_status()

            # Try to get detailed battery status
            # Venus E 3 may not support this, fallback to ES data
            bat_data = None
            try:
                _LOGGER.debug("Fetching battery status")
                bat_data = await self.client.get_bat_status()
                # Map bat_capacity to show TOTAL capacity (rated_capacity)
                # bat_capacity from Bat.GetStatus is "remaining" not "total"
                if bat_data and "rated_capacity" in bat_data:
                    bat_data["bat_capacity"] = bat_data["rated_capacity"]
            except (MarstekConnectionError, MarstekApiError, TimeoutError, Exception) as err:
                _LOGGER.debug("Bat.GetStatus not available, using ES data: %s", err)
                # Fallback: Use ES data for battery sensors
                bat_data = {
                    "soc": es_data.get("bat_soc"),
                    "bat_capacity": es_data.get("bat_cap"),  # This is total capacity from ES
                    # Other battery fields not available on Venus E 3
                    "charg_flag": None,
                    "dischrg_flag": None,
                    "bat_temp": None,
                    "rated_capacity": es_data.get("bat_cap"),  # Same as bat_capacity
                }

            # Try to get operating mode
            # May not be supported on all Venus E 3 hardware revisions
            # Note: Rate limiting is handled automatically by the API client
            mode_data = None
            try:
                _LOGGER.debug("Fetching operating mode")
                mode_data = await self.client.get_mode()
            except Exception as err:
                _LOGGER.debug("Operating mode not available: %s", err)
                # Fallback mode data if not supported
                mode_data = {
                    "mode": "Unknown",
                    "ongrid_power": es_data.get("ongrid_power"),
                    "offgrid_power": es_data.get("offgrid_power"),
                    "bat_soc": es_data.get("bat_soc"),
                }

            # Try to get energy meter data
            # This may fail if CT sensors are not connected
            # Note: Rate limiting is handled automatically by the API client
            em_data = None
            try:
                _LOGGER.debug("Fetching energy meter status")
                em_data = await self.client.get_em_status()
            except (MarstekConnectionError, MarstekApiError, TimeoutError, Exception) as err:
                _LOGGER.debug("Energy meter not available: %s", err)

            # Skip optional API calls to reduce update time
            # WiFi, Bluetooth, and PV status rarely change and take extra time
            # These can be added back if needed, but would increase update cycle to 17+ seconds
            wifi_data = None
            ble_data = None
            pv_data = None

            # Return all the data as a dictionary
            # Entities will access this via self.coordinator.data
            return {
                "es": es_data,
                "bat": bat_data,
                "mode": mode_data,
                "em": em_data,
                "wifi": wifi_data,
                "ble": ble_data,
                "pv": pv_data,
            }

        except MarstekConnectionError as err:
            # Connection error - device may be offline
            raise UpdateFailed(f"Connection error: {err}") from err

        except MarstekApiError as err:
            # API error - device returned error
            raise UpdateFailed(f"API error: {err}") from err

        except Exception as err:
            # Unexpected error
            _LOGGER.exception("Unexpected error updating data: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err
