"""Time platform for Marstek Venus E: start/end of Manual schedule slots."""

import logging
from datetime import time as dt_time
from typing import Any, Dict

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NUM_SCHEDULE_SLOTS
from .coordinator import MarstekDataUpdateCoordinator
from .slot_entity import ScheduleSlotEntity

_LOGGER = logging.getLogger(__name__)


def _parse(value: str) -> dt_time:
    """Parse an ``HH:MM`` string into a time, defaulting to 00:00."""
    try:
        hour, minute = value.split(":")
        return dt_time(int(hour), int(minute))
    except (ValueError, AttributeError):
        return dt_time(0, 0)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the per-slot start/end time entities."""
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

    entities = []
    for i in range(NUM_SCHEDULE_SLOTS):
        entities.append(SlotTime(coordinator, wifi_mac, i, dev, "start"))
        entities.append(SlotTime(coordinator, wifi_mac, i, dev, "end"))
    async_add_entities(entities)


class SlotTime(ScheduleSlotEntity, TimeEntity):
    """Start or end time of one Manual schedule slot."""

    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, wifi_mac, index, device_info, field: str) -> None:
        super().__init__(coordinator, wifi_mac, index, device_info, field)
        self._field = field
        self._attr_name = f"Slot {index + 1} {field}"

    @property
    def native_value(self) -> dt_time:
        return _parse(self.slot.get(self._field, "00:00"))

    async def async_set_value(self, value: dt_time) -> None:
        await self.async_apply_change(
            **{self._field: f"{value.hour:02d}:{value.minute:02d}"}
        )
