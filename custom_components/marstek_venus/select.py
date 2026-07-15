"""Select platform for Marstek Venus E."""
import asyncio
import logging
from typing import Any, Dict, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .api import MarstekApiClient, MarstekApiError
from .const import (
    DAY_PRESET_EVERYDAY,
    DAY_PRESET_LABELS,
    DOMAIN,
    MODE_AI,
    MODE_AUTO,
    MODE_MANUAL,
    MODE_PASSIVE,
    MODES,
    NUM_SCHEDULE_SLOTS,
    normalize_mode,
)
from .coordinator import MarstekDataUpdateCoordinator
from .slot_entity import ScheduleSlotEntity

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

    # Create the mode select entity plus the per-slot day-preset selects.
    wifi_mac = device_info.get("wifi_mac", "unknown")
    model = device_info.get("device", "VenusE")
    dev = DeviceInfo(
        identifiers={(DOMAIN, wifi_mac)},
        name=f"Marstek {model}",
        manufacturer="Marstek",
        model=model,
        sw_version=str(device_info.get("ver", "Unknown")),
    )
    entities = [MarstekModeSelect(coordinator, client, entry, device_info)]
    entities += [
        SlotDaysSelect(coordinator, wifi_mac, i, dev)
        for i in range(NUM_SCHEDULE_SLOTS)
    ]
    async_add_entities(entities)

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

    platform.async_register_entity_service(
        "set_manual_schedules_bulk",
        {
            vol.Required("schedules"): [
                {
                    vol.Required("time_slot"): cv.positive_int,
                    vol.Required("start_time"): str,
                    vol.Required("end_time"): str,
                    vol.Required("power"): int,
                    vol.Required("days"): [str],
                    vol.Optional("enabled", default=True): cv.boolean,
                }
            ]
        },
        "async_set_manual_schedules_bulk",
    )

    platform.async_register_entity_service(
        "refresh_data",
        {},
        "async_refresh_data",
    )

    platform.async_register_entity_service(
        "test_connection",
        {},
        "async_test_connection",
        supports_response=SupportsResponse.OPTIONAL,
    )

    platform.async_register_entity_service(
        "get_mode_details",
        {},
        "async_get_mode_details",
        supports_response=SupportsResponse.OPTIONAL,
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

        # Set available options
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
    def current_option(self) -> Optional[str]:
        """
        Return the currently selected mode.

        Returns:
            The current mode string, or None if unknown (shown as unknown in
            the UI rather than misreporting a concrete mode).
        """
        if self.coordinator.data is None:
            return None

        # Normalize the raw device value; None (shown as unknown in the UI)
        # for anything unrecognised rather than misreporting a concrete mode.
        return normalize_mode(self.coordinator.data.get("mode", {}).get("mode"))

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

        # Manual power is driven by the coordinator (Charge/Discharge Power
        # numbers). Delegate so selecting Manual applies whatever setpoint is
        # currently held (0 W = idle manual).
        if option == MODE_MANUAL:
            # Manual mode runs the HA-owned schedule.
            if not await self.coordinator.async_apply_schedule():
                _LOGGER.warning(
                    "Cannot switch to Manual: no schedule slots are enabled. "
                    "Enable at least one slot, then apply."
                )
            return

        try:
            # Build the mode configuration based on selected option
            if option == MODE_AUTO:
                config = {"auto_cfg": {"enable": 1}}

            elif option == MODE_AI:
                config = {"ai_cfg": {"enable": 1}}

            elif option == MODE_PASSIVE:
                # Passive is countdown-based; the Charge/Discharge numbers use
                # Manual instead. Selecting Passive here is a raw one-shot at
                # 0 W that reverts when cd_time elapses. Use the
                # set_mode_passive service for a specific passive power.
                config = {"passive_cfg": {"power": 0, "cd_time": 300}}

            else:
                _LOGGER.error("Unknown mode selected: %s", option)
                return

            # Send the command to the device
            success = await self._client.set_mode(option, config)

            if not success:
                _LOGGER.error("Failed to set mode to %s", option)
                return

            # Left for another mode: reset the displayed Passive setpoints.
            self.coordinator.clear_passive_control()

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
        # Validation
        import re

        if not (0 <= time_slot <= 9):
            raise ValueError(f"time_slot must be 0-9, got {time_slot}")

        # Validate time format (HH:MM)
        time_pattern = re.compile(r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$')
        if not time_pattern.match(start_time):
            raise ValueError(f"start_time must be HH:MM format, got {start_time}")
        if not time_pattern.match(end_time):
            raise ValueError(f"end_time must be HH:MM format, got {end_time}")

        # Validate power range (device specific)
        if not (-5000 <= power <= 5000):
            raise ValueError(f"power must be -5000 to 5000W, got {power}")

        # Validate days
        valid_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        for day in days:
            if day.lower() not in valid_days:
                raise ValueError(f"Invalid day: {day}. Must be one of {valid_days}")

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

            # Switched to a non-Manual mode via a service: reset the displayed
            # Passive Charge/Discharge setpoints.
            if mode != MODE_MANUAL:
                self.coordinator.clear_passive_control()

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

    async def async_set_manual_schedules_bulk(self, schedules: list) -> None:
        """
        Set multiple manual mode schedules at once.

        Args:
            schedules: List of schedule dictionaries, each containing:
                - time_slot: int (0-9)
                - start_time: str (HH:MM)
                - end_time: str (HH:MM)
                - power: int (watts)
                - days: list of day codes
                - enabled: bool
        """
        _LOGGER.info("Setting %d manual schedules in bulk", len(schedules))

        for i, schedule in enumerate(schedules):
            try:
                await self.async_set_manual_mode(
                    time_slot=schedule["time_slot"],
                    start_time=schedule["start_time"],
                    end_time=schedule["end_time"],
                    power=schedule["power"],
                    days=schedule["days"],
                    enabled=schedule.get("enabled", True)
                )
                # Rate limiting handled by API client
                _LOGGER.debug("Set schedule %d/%d", i + 1, len(schedules))
            except Exception as err:
                _LOGGER.error("Failed to set schedule %d: %s", i, err)
                raise

    async def async_refresh_data(self) -> None:
        """Force refresh coordinator data."""
        _LOGGER.info("Manual data refresh requested")
        await self.coordinator.async_request_refresh()

    async def async_test_connection(self) -> Dict[str, Any]:
        """
        Test connection to device and return diagnostics.

        Returns:
            Dictionary with connection test results
        """
        import time
        _LOGGER.info("Testing connection to device")

        results = {
            "success": False,
            "ping_time_ms": None,
            "device_reachable": False,
            "api_responsive": False,
            "error": None
        }

        try:
            start = time.monotonic()
            device_info = await self._client.get_device_info()
            duration_ms = (time.monotonic() - start) * 1000

            results["success"] = True
            results["ping_time_ms"] = round(duration_ms, 1)
            results["device_reachable"] = True
            results["api_responsive"] = True
            results["firmware_version"] = device_info.get("ver")
            results["device_model"] = device_info.get("device")

            _LOGGER.info("Connection test successful: %s ms", results["ping_time_ms"])

        except Exception as err:
            results["error"] = str(err)
            _LOGGER.error("Connection test failed: %s", err)

        # Fire event with results so automation can respond
        self.hass.bus.fire(
            f"{DOMAIN}_connection_test",
            {
                "entity_id": self.entity_id,
                "results": results
            }
        )

        return results

    async def async_get_mode_details(self) -> Dict[str, Any]:
        """
        Get detailed current mode configuration.

        Returns:
            Dictionary with current mode details from ES.GetMode
        """
        _LOGGER.info("Getting current mode details")

        try:
            mode_data = await self._client.get_mode()

            details = {
                "mode": mode_data.get("mode", "Unknown"),
                "ongrid_power": mode_data.get("ongrid_power"),
                "offgrid_power": mode_data.get("offgrid_power"),
                "battery_soc": mode_data.get("bat_soc"),
            }

            # Fire event with details
            self.hass.bus.fire(
                f"{DOMAIN}_mode_details",
                {
                    "entity_id": self.entity_id,
                    "details": details
                }
            )

            return details

        except Exception as err:
            _LOGGER.error("Failed to get mode details: %s", err)
            raise


class SlotDaysSelect(ScheduleSlotEntity, SelectEntity):
    """Day-of-week preset for one Manual schedule slot."""

    _attr_icon = "mdi:calendar-week"

    def __init__(self, coordinator, wifi_mac, index, device_info) -> None:
        super().__init__(coordinator, wifi_mac, index, device_info, "days")
        self._attr_name = f"Slot {index + 1} days"
        self._attr_options = list(DAY_PRESET_LABELS.values())
        self._label_to_key = {label: key for key, label in DAY_PRESET_LABELS.items()}

    @property
    def current_option(self) -> str:
        return DAY_PRESET_LABELS.get(
            self.slot.get("days"), DAY_PRESET_LABELS[DAY_PRESET_EVERYDAY]
        )

    async def async_select_option(self, option: str) -> None:
        key = self._label_to_key.get(option)
        if key:
            await self.async_apply_change(days=key)
