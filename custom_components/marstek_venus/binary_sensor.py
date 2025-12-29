"""Binary sensor platform for Marstek Venus E."""
import logging
from typing import Any, Dict

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
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
    """Set up Marstek Venus E binary sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: MarstekDataUpdateCoordinator = data["coordinator"]
    device_info_dict: Dict[str, Any] = data["device_info"]

    # Extract device identifiers
    wifi_mac = device_info_dict.get("wifi_mac", "unknown")
    device_model = device_info_dict.get("device", "VenusE")

    # Create device info
    main_device_info = DeviceInfo(
        identifiers={(DOMAIN, wifi_mac)},
        name=f"Marstek {device_model}",
        manufacturer="Marstek",
        model=device_model,
        sw_version=str(device_info_dict.get("ver", "Unknown")),
    )

    # Create binary sensor entities
    entities = [
        ConnectionStatusBinarySensor(coordinator, entry, device_info_dict, main_device_info),
    ]

    async_add_entities(entities)


class ConnectionStatusBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for connection status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)

        self._attr_has_entity_name = True
        wifi_mac = device_info_dict.get("wifi_mac", "unknown")

        self._attr_unique_id = f"{wifi_mac}_connection"
        self._attr_name = "Connection"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        """Return true if connected."""
        # Coordinator is available when last update succeeded
        return self.coordinator.last_update_success
