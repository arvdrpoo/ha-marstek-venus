"""Select platform for Marstek Venus E."""
import asyncio
import logging
from typing import Any, Dict

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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

        # Track if mode control is supported
        self._mode_control_supported = True

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._mode_control_supported

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
                "Timeout setting mode to %s. Your Venus E 3 hardware does not support "
                "mode control (ES.SetMode). The mode selector entity will be disabled.",
                option
            )
            # Disable the entity since mode control is not supported
            self._mode_control_supported = False
            self.async_write_ha_state()

        except MarstekApiError as err:
            _LOGGER.error("Error setting mode: %s", err)
