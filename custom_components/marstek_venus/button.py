"""Button platform for Marstek Venus E: apply the HA-owned schedule."""

import logging
from typing import Any, Dict

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MarstekDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Apply-schedule button."""
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

    async_add_entities([ApplyScheduleButton(coordinator, wifi_mac, dev)])


class ApplyScheduleButton(CoordinatorEntity, ButtonEntity):
    """Write the HA-owned schedule to the device (switches it to Manual).

    Editing the slot entities only changes HA-local state; pressing this pushes
    every enabled slot to the device via ES.SetMode (and clears the others), so
    the device's Manual table matches what you configured in HA.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, coordinator, wifi_mac, device_info) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{wifi_mac}_apply_schedule"
        self._attr_name = "Apply schedule"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        await self.coordinator.async_apply_schedule(full=True)
