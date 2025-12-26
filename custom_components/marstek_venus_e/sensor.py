"""Sensor platform for Marstek Venus E."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
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
    """
    Set up Marstek Venus E sensors from a config entry.

    This function is called by Home Assistant to create all sensor entities.

    Args:
        hass: Home Assistant instance
        entry: The config entry
        async_add_entities: Callback to add entities
    """
    # Get the coordinator from hass.data
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: MarstekDataUpdateCoordinator = data["coordinator"]
    device_info: Dict[str, Any] = data["device_info"]

    # Create all sensor entities
    entities = [
        # Battery sensors
        BatterySocSensor(coordinator, entry, device_info),
        BatteryCapacitySensor(coordinator, entry, device_info),
        BatteryPowerSensor(coordinator, entry, device_info),
        BatteryTemperatureSensor(coordinator, entry, device_info),

        # Power flow sensors
        PvPowerSensor(coordinator, entry, device_info),
        GridPowerSensor(coordinator, entry, device_info),
        LoadPowerSensor(coordinator, entry, device_info),

        # Energy total sensors
        TotalPvEnergySensor(coordinator, entry, device_info),
        TotalGridInputEnergySensor(coordinator, entry, device_info),
        TotalGridOutputEnergySensor(coordinator, entry, device_info),
        TotalLoadEnergySensor(coordinator, entry, device_info),
    ]

    # Add all entities to Home Assistant
    async_add_entities(entities)


class MarstekSensorBase(CoordinatorEntity, SensorEntity):
    """
    Base class for all Marstek sensors.

    CoordinatorEntity provides:
    - Automatic updates when coordinator data changes
    - Automatic availability based on coordinator state
    - Efficient data sharing (all entities use same coordinator)

    All specific sensor classes inherit from this base.
    """

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
        sensor_type: str,
        name: str,
    ) -> None:
        """
        Initialize the sensor.

        Args:
            coordinator: The data update coordinator
            entry: Config entry
            device_info: Device information dictionary
            sensor_type: Unique identifier for this sensor type
            name: Human-readable name for the sensor
        """
        super().__init__(coordinator)

        # Extract device identifiers
        self._attr_has_entity_name = True
        wifi_mac = device_info.get("wifi_mac", "unknown")
        device_model = device_info.get("device", "VenusE")

        # Set unique ID (required for entities)
        # Format: {wifi_mac}_{sensor_type}
        self._attr_unique_id = f"{wifi_mac}_{sensor_type}"

        # Set entity name
        self._attr_name = name

        # Link this entity to the device in the device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, wifi_mac)},
            name=f"Marstek {device_model}",
            manufacturer="Marstek",
            model=device_model,
            sw_version=str(device_info.get("ver", "Unknown")),
        )

    def _get_value(self, *keys: str, default: Any = None) -> Any:
        """
        Safely get a value from nested coordinator data.

        Example:
            self._get_value("bat", "soc")  # Gets coordinator.data["bat"]["soc"]

        Args:
            *keys: Keys to traverse in the data dictionary
            default: Default value if key doesn't exist

        Returns:
            The value at the specified path, or default if not found
        """
        data = self.coordinator.data
        for key in keys:
            if not isinstance(data, dict):
                return default
            data = data.get(key)
            if data is None:
                return default
        return data


# ============================================================================
# Battery Sensors
# ============================================================================


class BatterySocSensor(MarstekSensorBase):
    """Battery State of Charge sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info, "battery_soc", "Battery")

        # Set sensor attributes
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("bat", "soc")


class BatteryCapacitySensor(MarstekSensorBase):
    """Battery Capacity sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info, "battery_capacity", "Battery Capacity")

        self._attr_device_class = SensorDeviceClass.ENERGY_STORAGE
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("bat", "bat_capacity")


class BatteryPowerSensor(MarstekSensorBase):
    """Battery Power sensor (positive=charging, negative=discharging)."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info, "battery_power", "Battery Power")

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("es", "bat_power")


class BatteryTemperatureSensor(MarstekSensorBase):
    """Battery Temperature sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info, "battery_temperature", "Battery Temperature")

        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("bat", "bat_temp")


# ============================================================================
# Power Flow Sensors
# ============================================================================


class PvPowerSensor(MarstekSensorBase):
    """Solar (PV) Power sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info, "pv_power", "Solar Power")

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("es", "pv_power")


class GridPowerSensor(MarstekSensorBase):
    """Grid Power sensor (positive=exporting, negative=importing)."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info, "grid_power", "Grid Power")

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("es", "ongrid_power")


class LoadPowerSensor(MarstekSensorBase):
    """Load (Off-grid) Power sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info, "load_power", "Load Power")

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("es", "offgrid_power")


# ============================================================================
# Energy Total Sensors
# ============================================================================


class TotalPvEnergySensor(MarstekSensorBase):
    """Total Solar Energy Generated sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info, "total_pv_energy", "Total Solar Energy")

        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("es", "total_pv_energy")


class TotalGridInputEnergySensor(MarstekSensorBase):
    """Total Grid Input Energy sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info, "total_grid_input_energy", "Total Grid Import Energy")

        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("es", "total_grid_input_energy")


class TotalGridOutputEnergySensor(MarstekSensorBase):
    """Total Grid Output Energy sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info, "total_grid_output_energy", "Total Grid Export Energy")

        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("es", "total_grid_output_energy")


class TotalLoadEnergySensor(MarstekSensorBase):
    """Total Load Energy Consumed sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info, "total_load_energy", "Total Load Energy")

        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("es", "total_load_energy")
