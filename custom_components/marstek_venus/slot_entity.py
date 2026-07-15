"""Base entity for the HA-owned Manual schedule slots.

Schedule slots are Home-Assistant-owned configuration (the local API cannot read
the device's slot table back), so these entities stay available even when the
device is offline: you can edit the schedule any time, and pushing it to the
device is a separate step (the Apply button, or auto re-assert on recovery).
"""

from __future__ import annotations

from typing import Any, Dict

from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class ScheduleSlotEntity(CoordinatorEntity):
    """Base for entities that view/edit one Manual schedule slot."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, wifi_mac: str, index: int, device_info, key: str) -> None:
        """Initialize the slot entity.

        Args:
            coordinator: The data update coordinator (holds the schedule).
            wifi_mac: Device identity, for the unique_id.
            index: Slot index (also the device time_num).
            device_info: DeviceInfo linking the entity to the main device.
            key: Short field key, for a stable unique_id.
        """
        super().__init__(coordinator)
        self._index = index
        self._attr_unique_id = f"{wifi_mac}_slot{index}_{key}"
        self._attr_device_info = device_info

    @property
    def slot(self) -> Dict[str, Any]:
        """Return this entity's slot dict from the coordinator's schedule."""
        return self.coordinator.schedule[self._index]

    @property
    def available(self) -> bool:
        """Schedule editing is local, so slots are always available."""
        return True

    async def async_apply_change(self, **changes: Any) -> None:
        """Update this slot's fields in HA and persist (no device write)."""
        self.coordinator.schedule[self._index].update(changes)
        await self.coordinator.async_save_schedule()
