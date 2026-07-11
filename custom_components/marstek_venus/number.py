"""Number platform for Marstek Venus E: Manual-mode power control.

Exposes two mutually exclusive setpoints, Charge Power and Discharge Power, that
drive the device's Manual mode (time slot 0, all day), the same mechanism the
Marstek app uses for continuous manual power. Setting either to a non-zero value
puts the device into Manual control at that power; it holds until changed (no
countdown). Setting both to zero holds Manual at idle; to hand control back to
Auto/AI, use the Operating Mode select.
"""
import logging
from typing import Any, Dict

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MAX_PASSIVE_POWER,
    PASSIVE_POWER_STEP,
)
from .coordinator import MarstekDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Passive charge/discharge number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: MarstekDataUpdateCoordinator = data["coordinator"]
    device_info: Dict[str, Any] = data["device_info"]

    wifi_mac = device_info.get("wifi_mac", "unknown")
    device_model = device_info.get("device", "VenusE")

    main_device_info = DeviceInfo(
        identifiers={(DOMAIN, wifi_mac)},
        name=f"Marstek {device_model}",
        manufacturer="Marstek",
        model=device_model,
        sw_version=str(device_info.get("ver", "Unknown")),
    )

    async_add_entities(
        [
            ChargePowerNumber(coordinator, wifi_mac, main_device_info),
            DischargePowerNumber(coordinator, wifi_mac, main_device_info),
        ]
    )


class _ManualPowerNumber(CoordinatorEntity, RestoreNumber):
    """Base for the Manual charge/discharge setpoint numbers.

    Uses RestoreNumber so the last setpoint is shown again after a restart.
    Restoring is deliberately display-only: it does not re-command the device.
    Manual mode persists on the device across restarts, so the displayed value
    is usually still what the device is doing; commanding only happens when the
    value is set again (or via the Operating Mode select).
    """

    _attr_has_entity_name = True
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_native_max_value = MAX_PASSIVE_POWER
    _attr_native_step = PASSIVE_POWER_STEP
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        wifi_mac: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{wifi_mac}_{self._key}"
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        """Restore the last setpoint into the coordinator (display only)."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._restore(int(last.native_value))

    def _restore(self, value: int) -> None:
        """Write a restored value into coordinator state without commanding."""
        raise NotImplementedError

    @property
    def native_value(self) -> float:
        """Return the current setpoint from coordinator state."""
        raise NotImplementedError


class ChargePowerNumber(_ManualPowerNumber):
    """Manual-mode charge power setpoint (watts into the battery)."""

    _key = "charge_power"
    _attr_name = "Charge Power"
    _attr_icon = "mdi:battery-charging"

    def _restore(self, value: int) -> None:
        self.coordinator.manual_charge_power = value

    @property
    def native_value(self) -> float:
        return self.coordinator.manual_charge_power

    async def async_set_native_value(self, value: float) -> None:
        """Charge at the given power (forces discharge to 0)."""
        await self.coordinator.async_apply_manual(charge=int(value), discharge=0)


class DischargePowerNumber(_ManualPowerNumber):
    """Manual-mode discharge power setpoint (watts out of the battery)."""

    _key = "discharge_power"
    _attr_name = "Discharge Power"
    _attr_icon = "mdi:battery-arrow-down"

    def _restore(self, value: int) -> None:
        self.coordinator.manual_discharge_power = value

    @property
    def native_value(self) -> float:
        return self.coordinator.manual_discharge_power

    async def async_set_native_value(self, value: float) -> None:
        """Discharge at the given power (forces charge to 0)."""
        await self.coordinator.async_apply_manual(charge=0, discharge=int(value))
