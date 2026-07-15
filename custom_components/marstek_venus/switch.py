"""Switch platform for Marstek Venus E: enable/disable Manual schedule slots."""

import logging
from typing import Any, Dict

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NUM_SCHEDULE_SLOTS
from .coordinator import MarstekDataUpdateCoordinator
from .slot_entity import ScheduleSlotEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the per-slot enable switches."""
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

    async_add_entities(
        SlotEnableSwitch(coordinator, wifi_mac, i, dev)
        for i in range(NUM_SCHEDULE_SLOTS)
    )


class SlotEnableSwitch(ScheduleSlotEntity, SwitchEntity):
    """Enable/disable one Manual schedule slot (HA-side; apply to push)."""

    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator, wifi_mac, index, device_info) -> None:
        super().__init__(coordinator, wifi_mac, index, device_info, "enable")
        self._attr_name = f"Slot {index + 1} enabled"

    @property
    def is_on(self) -> bool:
        return bool(self.slot.get("enable"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.async_apply_change(enable=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_apply_change(enable=False)
