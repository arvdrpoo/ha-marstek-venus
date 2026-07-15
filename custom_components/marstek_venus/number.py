"""Number platform for Marstek Venus E.

Two groups of number entities:

- **Passive quick-control** (Charge Power, Discharge Power, Passive Duration):
  a temporary "charge/discharge now" override driven by Passive mode. Passive
  holds the power for the configured duration, then the device reverts on its
  own, so this never touches the Manual schedule slots.

- **Schedule slot power** (Slot N power): the power for each HA-owned Manual
  schedule slot. Signed: negative = charge, positive = discharge. Editing is
  HA-local; use the Apply Schedule button to push it to the device.
"""

import logging
from typing import Any, Dict

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MAX_MANUAL_POWER,
    MAX_PASSIVE_COUNTDOWN,
    MAX_PASSIVE_POWER,
    MIN_PASSIVE_COUNTDOWN,
    NUM_SCHEDULE_SLOTS,
    PASSIVE_POWER_STEP,
)
from .coordinator import MarstekDataUpdateCoordinator
from .slot_entity import ScheduleSlotEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Passive quick-control and schedule-slot power numbers."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: MarstekDataUpdateCoordinator = data["coordinator"]
    device_info: Dict[str, Any] = data["device_info"]

    wifi_mac = device_info.get("wifi_mac", "unknown")
    model = device_info.get("device", "VenusE")
    dev = DeviceInfo(
        identifiers={(DOMAIN, wifi_mac)},
        name=f"Marstek {model}",
        manufacturer="Marstek",
        model=model,
        sw_version=str(device_info.get("ver", "Unknown")),
    )

    entities: list = [
        ChargePowerNumber(coordinator, wifi_mac, dev),
        DischargePowerNumber(coordinator, wifi_mac, dev),
        PassiveDurationNumber(coordinator, wifi_mac, dev),
    ]
    entities += [
        SlotPowerNumber(coordinator, wifi_mac, i, dev)
        for i in range(NUM_SCHEDULE_SLOTS)
    ]
    async_add_entities(entities)


class _PassivePowerNumber(CoordinatorEntity, RestoreNumber):
    """Base for the Passive charge/discharge setpoint numbers.

    Uses RestoreNumber so the last setpoint is shown again after a restart.
    Restoring is display-only: it does not re-command the device. Passive
    reverts on its own after the countdown, so the displayed value only reflects
    the last commanded setpoint; commanding happens when the value is set.
    """

    _attr_has_entity_name = True
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_native_max_value = MAX_PASSIVE_POWER
    _attr_native_step = PASSIVE_POWER_STEP
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, wifi_mac, device_info) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{wifi_mac}_{self._key}"
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._restore(int(last.native_value))

    def _restore(self, value: int) -> None:
        raise NotImplementedError

    @property
    def native_value(self) -> float:
        raise NotImplementedError


class ChargePowerNumber(_PassivePowerNumber):
    """Passive-mode charge power (watts into the battery, held for the duration)."""

    _key = "charge_power"
    _attr_name = "Charge Power"
    _attr_icon = "mdi:battery-charging"

    def _restore(self, value: int) -> None:
        self.coordinator.passive_charge_power = value

    @property
    def native_value(self) -> float:
        return self.coordinator.passive_charge_power

    async def async_set_native_value(self, value: float) -> None:
        """Charge at the given power for the Passive duration (discharge -> 0)."""
        await self.coordinator.async_apply_passive(charge=int(value), discharge=0)


class DischargePowerNumber(_PassivePowerNumber):
    """Passive-mode discharge power (watts out of the battery, held for the duration)."""

    _key = "discharge_power"
    _attr_name = "Discharge Power"
    _attr_icon = "mdi:battery-arrow-down"

    def _restore(self, value: int) -> None:
        self.coordinator.passive_discharge_power = value

    @property
    def native_value(self) -> float:
        return self.coordinator.passive_discharge_power

    async def async_set_native_value(self, value: float) -> None:
        """Discharge at the given power for the Passive duration (charge -> 0)."""
        await self.coordinator.async_apply_passive(charge=0, discharge=int(value))


class PassiveDurationNumber(CoordinatorEntity, RestoreNumber):
    """How long a Passive charge/discharge setpoint holds, in minutes.

    Display/config only: changing it does not command the device. It is applied
    the next time a Charge/Discharge Power value is set.
    """

    _attr_has_entity_name = True
    _attr_name = "Passive Duration"
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = MIN_PASSIVE_COUNTDOWN / 60
    _attr_native_max_value = MAX_PASSIVE_COUNTDOWN / 60
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, wifi_mac, device_info) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{wifi_mac}_passive_duration"
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self.coordinator.passive_countdown = int(last.native_value) * 60

    @property
    def native_value(self) -> float:
        return self.coordinator.passive_countdown / 60

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.passive_countdown = int(value) * 60
        self.async_write_ha_state()


class SlotPowerNumber(ScheduleSlotEntity, NumberEntity):
    """Power for one Manual schedule slot; negative = charge, positive = discharge."""

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = -MAX_MANUAL_POWER
    _attr_native_max_value = MAX_MANUAL_POWER
    _attr_native_step = 50
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator, wifi_mac, index, device_info) -> None:
        super().__init__(coordinator, wifi_mac, index, device_info, "power")
        self._attr_name = f"Slot {index + 1} power"

    @property
    def native_value(self) -> float:
        return float(self.slot.get("power", 0))

    async def async_set_native_value(self, value: float) -> None:
        await self.async_apply_change(power=int(value))
