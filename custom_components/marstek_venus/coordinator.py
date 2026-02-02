"""Data update coordinator for Marstek Venus E."""

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import MarstekApiClient, MarstekApiError, MarstekConnectionError
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Maximum consecutive failures before attempting reconnection
MAX_CONSECUTIVE_FAILURES = 5


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
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """
        Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            client: The API client for device communication
            device_info: Basic device information from initial connection
            scan_interval: Update interval in seconds
        """
        self.client = client
        self.device_info = device_info

        # Statistics tracking for diagnostics
        self._stats = {
            "request_count": 0,
            "error_count": 0,
            "total_response_time": 0.0,
            "last_update_success": None,
            "last_update_duration": None,
        }

        # Track consecutive failures for resilience
        self._consecutive_failures = 0
        self._last_successful_data: Optional[Dict[str, Any]] = None
        self._last_es_error: Optional[str] = None

        # Initialize the parent DataUpdateCoordinator
        # The name appears in debug logs
        super().__init__(
            hass,
            _LOGGER,
            name="Marstek Venus E",
            update_interval=timedelta(seconds=scan_interval),
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get diagnostic statistics."""
        avg_response_time = 0.0
        if self._stats["request_count"] > 0:
            avg_response_time = (
                self._stats["total_response_time"] / self._stats["request_count"]
            )

        # Include API-level diagnostics
        api_diagnostics = self.client.get_diagnostics()

        return {
            "request_count": self._stats["request_count"],
            "error_count": self._stats["error_count"],
            "average_response_time": round(avg_response_time, 2),
            "error_rate": round(
                (self._stats["error_count"] / self._stats["request_count"] * 100)
                if self._stats["request_count"] > 0
                else 0.0,
                2,
            ),
            "last_update_success": self._stats["last_update_success"],
            "last_update_duration": self._stats["last_update_duration"],
            "consecutive_failures": self._consecutive_failures,
            "last_es_error": self._last_es_error,
            "api_diagnostics": api_diagnostics,
        }

    def update_scan_interval(self, seconds: int) -> None:
        """Update the scan interval."""
        self.update_interval = timedelta(seconds=seconds)

    async def _attempt_reconnect(self) -> bool:
        """
        Attempt to reconnect to the device.

        Returns:
            True if reconnection was successful, False otherwise.
        """
        _LOGGER.info(
            "Attempting to reconnect to Marstek device at %s:%s",
            self.client.host,
            self.client.port,
        )
        try:
            await self.client.close()
            await asyncio.sleep(2)  # Wait before reconnecting
            await self.client.connect()
            _LOGGER.info("Successfully reconnected to Marstek device")
            return True
        except Exception as err:
            _LOGGER.error("Reconnection failed: %s", err)
            return False

    async def _async_update_data(self) -> Dict[str, Any]:
        """
        Fetch data from the device.

        This method is called automatically by Home Assistant at the
        configured update_interval. It should:
        1. Fetch all necessary data from the device
        2. Return a dictionary with all the data
        3. Raise UpdateFailed if something goes wrong

        The method is resilient to transient failures:
        - Uses cached data when ES.GetStatus fails temporarily
        - Attempts reconnection after multiple consecutive failures
        - Only raises UpdateFailed after exhausting recovery options

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
            UpdateFailed: If data fetch fails and no recovery is possible
        """
        start_time = time.monotonic()

        self._stats["request_count"] += 1

        # Fetch data from API endpoints
        # Note: Venus E 3 only supports some endpoints, not all from the docs

        # Try to get ES data - this is the critical endpoint
        es_data = None
        es_error = None

        try:
            _LOGGER.debug("Fetching energy system status")
            es_data = await self.client.get_es_status()
            self._last_es_error = None
            self._consecutive_failures = 0
        except (
            MarstekConnectionError,
            MarstekApiError,
            asyncio.TimeoutError,
            TimeoutError,
        ) as err:
            es_error = err
            self._last_es_error = str(err)
            self._consecutive_failures += 1

            _LOGGER.warning(
                "ES.GetStatus failed (attempt %d/%d): %s",
                self._consecutive_failures,
                MAX_CONSECUTIVE_FAILURES,
                err,
            )

            # If we have too many consecutive failures, try reconnecting
            if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                _LOGGER.warning(
                    "Too many consecutive failures (%d), attempting reconnect",
                    self._consecutive_failures,
                )
                if await self._attempt_reconnect():
                    # Try once more after reconnection
                    try:
                        es_data = await self.client.get_es_status()
                        self._last_es_error = None
                        self._consecutive_failures = 0
                        _LOGGER.info("ES.GetStatus succeeded after reconnection")
                    except Exception as retry_err:
                        _LOGGER.error(
                            "ES.GetStatus still failing after reconnect: %s", retry_err
                        )
                        es_error = retry_err

        # If ES data fetch failed, handle gracefully
        if es_data is None:
            self._stats["error_count"] += 1
            self._stats["last_update_success"] = False
            self._stats["last_update_duration"] = round(
                time.monotonic() - start_time, 2
            )

            # If we have cached data, return it with a warning
            if self._last_successful_data is not None:
                _LOGGER.warning(
                    "Using cached data due to ES.GetStatus failure: %s", es_error
                )
                # Return cached data but mark it as stale
                cached = self._last_successful_data.copy()
                cached["_stale"] = True
                cached["_error"] = str(es_error)
                return cached

            # No cached data available - must fail
            error_msg = f"ES.GetStatus failed: {es_error}"
            if isinstance(es_error, asyncio.TimeoutError):
                raise UpdateFailed(f"Timeout: {error_msg}") from es_error
            elif isinstance(es_error, MarstekApiError):
                raise UpdateFailed(f"API error: {error_msg}") from es_error
            elif isinstance(es_error, MarstekConnectionError):
                raise UpdateFailed(f"Connection error: {error_msg}") from es_error
            else:
                raise UpdateFailed(error_msg) from es_error

        # ES data fetched successfully, now get optional data
        # Try to get detailed battery status
        # Venus E 3 may not support this, fallback to ES data
        bat_data = None
        try:
            _LOGGER.debug("Fetching battery status")
            bat_data = await self.client.get_bat_status()
        except Exception as err:
            _LOGGER.debug("Bat.GetStatus not available, using ES data: %s", err)
            # Fallback: Use ES data for battery sensors
            bat_data = {
                "soc": es_data.get("bat_soc"),
                "bat_capacity": None,  # Remaining capacity not available
                # Other battery fields not available on Venus E 3
                "charg_flag": None,
                "dischrg_flag": None,
                "bat_temp": None,
                "rated_capacity": None,
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
        except Exception as err:
            _LOGGER.debug("Energy meter not available: %s", err)

        # Skip optional API calls to reduce update time
        # WiFi, Bluetooth, and PV status rarely change and take extra time
        # These can be added back if needed, but would increase update cycle to 17+ seconds
        wifi_data = None
        ble_data = None
        pv_data = None

        # Track success
        duration = time.monotonic() - start_time
        self._stats["total_response_time"] += duration
        self._stats["last_update_success"] = True
        self._stats["last_update_duration"] = round(duration, 2)

        # Build result data
        result = {
            "es": es_data,
            "bat": bat_data,
            "mode": mode_data,
            "em": em_data,
            "wifi": wifi_data,
            "ble": ble_data,
            "pv": pv_data,
        }

        # Cache successful data for resilience
        self._last_successful_data = result.copy()

        # Return all the data as a dictionary
        # Entities will access this via self.coordinator.data
        return result
