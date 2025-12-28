"""Select platform for Marstek Venus E."""
import asyncio
import logging
from typing import Any, Dict

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .api import MarstekApiClient, MarstekApiError
from .const import DOMAIN, MODE_AI, MODE_AUTO, MODE_MANUAL, MODE_PASSIVE, MODES
from .coordinator import MarstekDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Set up Marstek Venus E select entities from a config entry.

    This function creates the operating mode select entity.

    Args:
        hass: Home Assistant instance
        entry: The config entry
        async_add_entities: Callback to add entities
    """
    # Get the coordinator and client from hass.data
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: MarstekDataUpdateCoordinator = data["coordinator"]
    client: MarstekApiClient = data["client"]
    device_info: Dict[str, Any] = data["device_info"]

    # Create the mode select entity
    async_add_entities([MarstekModeSelect(coordinator, client, entry, device_info)])

    # Register entity platform services for advanced mode control
    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        "set_mode_auto",
        {},
        "async_set_auto_mode",
    )

    platform.async_register_entity_service(
        "set_mode_ai",
        {},
        "async_set_ai_mode",
    )

    platform.async_register_entity_service(
        "set_mode_manual",
        {
            vol.Required("time_slot"): cv.positive_int,
            vol.Required("start_time"): str,
            vol.Required("end_time"): str,
            vol.Required("power"): int,
            vol.Required("days"): [str],
            vol.Optional("enabled", default=True): cv.boolean,
        },
        "async_set_manual_mode",
    )

    platform.async_register_entity_service(
        "set_mode_passive",
        {
            vol.Required("power"): int,
            vol.Required("countdown"): cv.positive_int,
        },
        "async_set_passive_mode",
    )


class MarstekModeSelect(CoordinatorEntity, SelectEntity):
    """
    Select entity for Marstek operating mode.

    This entity allows users to switch between operating modes:
    - Auto: Automatic mode
    - AI: AI-based optimization
    - Manual: Manual power control mode
    - Passive: Direct power control mode
    """

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        client: MarstekApiClient,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """
        Initialize the select entity.

        Args:
            coordinator: The data update coordinator
            client: The API client for sending commands
            entry: Config entry
            device_info: Device information dictionary
        """
        super().__init__(coordinator)

        self._client = client

        # Extract device identifiers
        self._attr_has_entity_name = True
        wifi_mac = device_info.get("wifi_mac", "unknown")
        device_model = device_info.get("device", "VenusE")

        # Set unique ID
        self._attr_unique_id = f"{wifi_mac}_operating_mode"

        # Set entity name
        self._attr_name = "Operating Mode"

        # Set available options (excluding Manual for v1)
        self._attr_options = MODES

        # Link to device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, wifi_mac)},
            name=f"Marstek {device_model}",
            manufacturer="Marstek",
            model=device_model,
            sw_version=str(device_info.get("ver", "Unknown")),
        )

        # Icon for the entity
        self._attr_icon = "mdi:battery-sync"

    @property
    def current_option(self) -> str:
        """
        Return the currently selected mode.

        Returns:
            The current mode string, or Auto if unknown
        """
        if self.coordinator.data is None:
            return MODE_AUTO

        mode = self.coordinator.data.get("mode", {}).get("mode")

        # If mode is not in our list (e.g., Manual), default to Auto
        if mode not in MODES:
            return MODE_AUTO

        return mode

    async def async_select_option(self, option: str) -> None:
        """
        Change the operating mode.

        This method is called when the user selects a new mode.
        It sends the appropriate command to the device and then
        refreshes the coordinator data.

        Args:
            option: The selected mode ("Auto", "AI", "Manual", or "Passive")
        """
        _LOGGER.info("Changing operating mode to: %s", option)

        try:
            # Build the mode configuration based on selected option
            if option == MODE_AUTO:
                config = {"auto_cfg": {"enable": 1}}

            elif option == MODE_AI:
                config = {"ai_cfg": {"enable": 1}}

            elif option == MODE_MANUAL:
                # Manual mode with complete default configuration
                # Sets to 0W power, all week, 00:00-23:59 (effectively standby)
                config = {
                    "manual_cfg": {
                        "time_num": 0,
                        "start_time": "00:00",
                        "end_time": "23:59",
                        "week_set": 127,  # All days (binary: 1111111)
                        "power": 0,
                        "enable": 1
                    }
                }

            elif option == MODE_PASSIVE:
                # Passive mode requires power and countdown parameters
                # Use defaults: 0W (standby) with 300 second countdown
                config = {"passive_cfg": {"power": 0, "cd_time": 300}}

            else:
                _LOGGER.error("Unknown mode selected: %s", option)
                return

            # Send the command to the device
            success = await self._client.set_mode(option, config)

            if not success:
                _LOGGER.error("Failed to set mode to %s", option)
                return

            # Refresh coordinator data to reflect the change
            await self.coordinator.async_request_refresh()

        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timeout setting mode to %s. Your Venus E 3 hardware may not support "
                "mode control (ES.SetMode).",
                option
            )

        except MarstekApiError as err:
            _LOGGER.error("Error setting mode: %s", err)

    async def async_set_auto_mode(self) -> None:
        """Set Auto mode via service call."""
        _LOGGER.info("Setting Auto mode via service call")
        config = {"auto_cfg": {"enable": 1}}
        await self._set_mode_internal(MODE_AUTO, config)

    async def async_set_ai_mode(self) -> None:
        """Set AI mode via service call."""
        _LOGGER.info("Setting AI mode via service call")
        config = {"ai_cfg": {"enable": 1}}
        await self._set_mode_internal(MODE_AI, config)

    async def async_set_manual_mode(
        self,
        time_slot: int,
        start_time: str,
        end_time: str,
        power: int,
        days: list,
        enabled: bool = True
    ) -> None:
        """
        Set Manual mode with full configuration via service call.

        Args:
            time_slot: Time period number (0-9)
            start_time: Start time in HH:MM format
            end_time: End time in HH:MM format
            power: Power setting in watts (negative = charge, positive = discharge)
            days: List of day codes (mon, tue, wed, thu, fri, sat, sun)
            enabled: Whether to enable this schedule
        """
        _LOGGER.info(
            "Setting Manual mode: slot %d, %s-%s, %dW, days=%s, enabled=%s",
            time_slot, start_time, end_time, power, days, enabled
        )

        # Convert day names to week_set bitmask
        # Bit 0 = Monday, Bit 6 = Sunday
        day_map = {
            "mon": 0, "tue": 1, "wed": 2, "thu": 3,
            "fri": 4, "sat": 5, "sun": 6
        }
        week_set = 0
        for day in days:
            if day.lower() in day_map:
                week_set |= (1 << day_map[day.lower()])

        config = {
            "manual_cfg": {
                "time_num": time_slot,
                "start_time": start_time,
                "end_time": end_time,
                "week_set": week_set,
                "power": power,
                "enable": 1 if enabled else 0
            }
        }
        await self._set_mode_internal(MODE_MANUAL, config)

    async def async_set_passive_mode(self, power: int, countdown: int) -> None:
        """
        Set Passive mode with power and countdown via service call.

        Args:
            power: Power setting in watts (negative = charge, positive = discharge)
            countdown: Duration in seconds
        """
        _LOGGER.info("Setting Passive mode: %dW for %ds", power, countdown)
        config = {"passive_cfg": {"power": power, "cd_time": countdown}}
        await self._set_mode_internal(MODE_PASSIVE, config)

    async def _set_mode_internal(self, mode: str, config: Dict[str, Any]) -> None:
        """
        Internal method to set mode with given configuration.

        Args:
            mode: Mode name
            config: Mode configuration dictionary
        """
        try:
            success = await self._client.set_mode(mode, config)

            if not success:
                _LOGGER.error("Failed to set mode to %s", mode)
                return

            # Refresh coordinator data
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Successfully set mode to %s", mode)

        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timeout setting mode to %s. Your Venus E 3 hardware may not support "
                "mode control (ES.SetMode).",
                mode
            )

        except MarstekApiError as err:
            _LOGGER.error("Error setting mode to %s: %s", mode, err)
