"""Data update coordinator for Marstek Venus E."""
import asyncio
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
                "bat": {...},     # Battery data
                "mode": {...},    # Current operating mode
                "em": {...}       # Energy meter data (or None)
            }

        Raises:
            UpdateFailed: If data fetch fails
        """
        try:
            # Fetch data from API endpoints
            # Note: Venus E 3 only supports some endpoints, not all from the docs

            _LOGGER.debug("Fetching energy system status")
            es_data = await self.client.get_es_status()

            # Venus E 3 doesn't support Bat.GetStatus, but ES.GetStatus includes battery data
            # Use ES data for battery sensors
            bat_data = {
                "soc": es_data.get("bat_soc"),
                "bat_capacity": es_data.get("bat_cap"),
                # Other battery fields not available on Venus E 3
                "charg_flag": None,
                "dischrg_flag": None,
                "bat_temp": None,
                "rated_capacity": None,
            }

            # Venus E 3 doesn't support ES.GetMode
            # Mode control not available on this model
            mode_data = {
                "mode": "Unknown",
                "ongrid_power": es_data.get("ongrid_power"),
                "offgrid_power": es_data.get("offgrid_power"),
                "bat_soc": es_data.get("bat_soc"),
            }

            # Try to get energy meter data
            # This may fail if CT sensors are not connected
            em_data = None
            try:
                # Venus E 3 requires 2+ seconds between requests
                await asyncio.sleep(2.5)

                _LOGGER.debug("Fetching energy meter status")
                em_data = await self.client.get_em_status()
            except (MarstekConnectionError, MarstekApiError) as err:
                _LOGGER.debug("Energy meter not available: %s", err)

            # Return all the data as a dictionary
            # Entities will access this via self.coordinator.data
            return {
                "es": es_data,
                "bat": bat_data,
                "mode": mode_data,
                "em": em_data,
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
