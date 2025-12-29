"""Sensor platform for Marstek Venus E."""
from datetime import datetime
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

    # Extract device identifiers for creating device info
    wifi_mac = device_info.get("wifi_mac", "unknown")
    device_model = device_info.get("device", "VenusE")

    # Create device info for main Marstek device
    main_device_info = DeviceInfo(
        identifiers={(DOMAIN, wifi_mac)},
        name=f"Marstek {device_model}",
        manufacturer="Marstek",
        model=device_model,
        sw_version=str(device_info.get("ver", "Unknown")),
    )

    # Create device info for CT Meter (separate device)
    ct_device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{wifi_mac}_ct")},
        name=f"Marstek {device_model} - CT Meter",
        manufacturer="Marstek",
        model="CT Clamps",
        via_device=(DOMAIN, wifi_mac),  # Link to main device
    )

    # Create all sensor entities
    # Note: Venus E 3 gets all data from ES.GetStatus
    # Some sensors may show 0 if features aren't connected (e.g., solar panels, load monitoring)
    entities = [
        # Battery sensors (from Bat.GetStatus / ES.GetStatus)
        BatterySocSensor(coordinator, entry, device_info, main_device_info),
        BatteryCapacitySensor(coordinator, entry, device_info, main_device_info),
        BatteryTotalCapacitySensor(coordinator, entry, device_info, main_device_info),
        BatteryPowerSensor(coordinator, entry, device_info, main_device_info),
        BatteryTemperatureSensor(coordinator, entry, device_info, main_device_info),
        BatteryChargeFlagSensor(coordinator, entry, device_info, main_device_info),
        BatteryDischargeFlagSensor(coordinator, entry, device_info, main_device_info),
        BatteryRatedCapacitySensor(coordinator, entry, device_info, main_device_info),
        BatteryStateSensor(coordinator, entry, device_info, main_device_info),

        # Power flow sensors (from ES.GetStatus)
        PvPowerSensor(coordinator, entry, device_info, main_device_info),
        GridPowerSensor(coordinator, entry, device_info, main_device_info),
        LoadPowerSensor(coordinator, entry, device_info, main_device_info),

        # PV (solar) sensors (from PV.GetStatus - Venus D only)
        PvVoltageSensor(coordinator, entry, device_info, main_device_info),
        PvCurrentSensor(coordinator, entry, device_info, main_device_info),

        # Energy total sensors (from ES.GetStatus)
        TotalPvEnergySensor(coordinator, entry, device_info, main_device_info),
        TotalGridInputEnergySensor(coordinator, entry, device_info, main_device_info),
        TotalGridOutputEnergySensor(coordinator, entry, device_info, main_device_info),
        TotalLoadEnergySensor(coordinator, entry, device_info, main_device_info),

        # Operating mode sensor (from ES.GetMode)
        OperatingModeSensor(coordinator, entry, device_info, main_device_info),

        # Energy meter sensors (from EM.GetStatus) - CT Meter device
        CtStateSensor(coordinator, entry, device_info, ct_device_info),
        PhaseAPowerSensor(coordinator, entry, device_info, ct_device_info),
        PhaseBPowerSensor(coordinator, entry, device_info, ct_device_info),
        PhaseCPowerSensor(coordinator, entry, device_info, ct_device_info),
        TotalCtPowerSensor(coordinator, entry, device_info, ct_device_info),

        # WiFi sensors (from WiFi.GetStatus)
        WifiSignalSensor(coordinator, entry, device_info, main_device_info),
        WifiSsidSensor(coordinator, entry, device_info, main_device_info),

        # Bluetooth sensor (from BLE.GetStatus)
        BluetoothStateSensor(coordinator, entry, device_info, main_device_info),

        # Diagnostic sensors (disabled by default)
        DiagnosticRequestCountSensor(coordinator, entry, device_info, main_device_info),
        DiagnosticErrorRateSensor(coordinator, entry, device_info, main_device_info),
        DiagnosticAvgResponseTimeSensor(coordinator, entry, device_info, main_device_info),
        DiagnosticLastUpdateTimeSensor(coordinator, entry, device_info, main_device_info),
        DiagnosticPingTimeSensor(coordinator, entry, device_info, main_device_info),
        DeviceFirmwareSensor(coordinator, entry, device_info, main_device_info),
        DeviceModelSensor(coordinator, entry, device_info, main_device_info),
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
        device_info_dict: Dict[str, Any],
        sensor_type: str,
        name: str,
        device_info: DeviceInfo,
    ) -> None:
        """
        Initialize the sensor.

        Args:
            coordinator: The data update coordinator
            entry: Config entry
            device_info_dict: Device information dictionary (for unique ID)
            sensor_type: Unique identifier for this sensor type
            name: Human-readable name for the sensor
            device_info: DeviceInfo object for linking to device
        """
        super().__init__(coordinator)

        # Extract device identifiers
        self._attr_has_entity_name = True
        wifi_mac = device_info_dict.get("wifi_mac", "unknown")

        # Set unique ID (required for entities)
        # Format: {wifi_mac}_{sensor_type}
        self._attr_unique_id = f"{wifi_mac}_{sensor_type}"

        # Set entity name
        self._attr_name = name

        # Link this entity to the device in the device registry
        self._attr_device_info = device_info

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
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "battery_soc", "Battery", device_info)

        # Set sensor attributes
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("bat", "soc")


class BatteryCapacitySensor(MarstekSensorBase):
    """Battery Remaining Capacity sensor (varies with SOC)."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "battery_capacity", "Battery Capacity", device_info)

        self._attr_device_class = SensorDeviceClass.ENERGY_STORAGE
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        # This is remaining capacity (Wh) from Bat.GetStatus
        return self._get_value("bat", "bat_capacity")


class BatteryTotalCapacitySensor(MarstekSensorBase):
    """Battery Total Capacity sensor from ES.GetStatus."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "battery_total_capacity", "Battery Total Capacity", device_info)

        self._attr_device_class = SensorDeviceClass.ENERGY_STORAGE
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        # This is total capacity (Wh) from ES.GetStatus
        return self._get_value("es", "bat_cap")


class BatteryPowerSensor(MarstekSensorBase):
    """Battery Power sensor (positive=charging, negative=discharging)."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "battery_power", "Battery Power", device_info)

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
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "battery_temperature", "Battery Temperature", device_info)

        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = True  # Enabled by default for battery health monitoring

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("bat", "bat_temp")


class BatteryChargeFlagSensor(MarstekSensorBase):
    """Battery Charging Permission Flag sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "battery_charge_flag", "Battery Charge Enabled", device_info)

        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["Enabled", "Disabled", "Unknown"]
        self._attr_entity_registry_enabled_default = False  # Disabled by default

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        flag = self._get_value("bat", "charg_flag")
        if flag is None:
            return "Unknown"
        return "Enabled" if flag else "Disabled"


class BatteryDischargeFlagSensor(MarstekSensorBase):
    """Battery Discharging Permission Flag sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "battery_discharge_flag", "Battery Discharge Enabled", device_info)

        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["Enabled", "Disabled", "Unknown"]
        self._attr_entity_registry_enabled_default = False  # Disabled by default

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        flag = self._get_value("bat", "dischrg_flag")
        if flag is None:
            return "Unknown"
        return "Enabled" if flag else "Disabled"


class BatteryRatedCapacitySensor(MarstekSensorBase):
    """Battery Rated Capacity sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "battery_rated_capacity", "Battery Rated Capacity", device_info)

        self._attr_device_class = SensorDeviceClass.ENERGY_STORAGE
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = False  # Disabled by default

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("bat", "rated_capacity")


class BatteryStateSensor(MarstekSensorBase):
    """Battery charging/discharging state sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, device_info_dict, "battery_state", "Battery State", device_info
        )

        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["Charging", "Discharging", "Idle", "Unknown"]
        self._attr_icon = "mdi:battery-arrow-up-down"

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        bat_power = self._get_value("es", "bat_power")

        if bat_power is None:
            return "Unknown"
        elif bat_power > 10:  # Threshold to avoid noise
            return "Charging"
        elif bat_power < -10:
            return "Discharging"
        else:
            return "Idle"


# ============================================================================
# Power Flow Sensors
# ============================================================================


class PvPowerSensor(MarstekSensorBase):
    """Solar (PV) Power sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "pv_power", "Solar Power", device_info)

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("es", "pv_power")


class PvVoltageSensor(MarstekSensorBase):
    """Solar (PV) Voltage sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "pv_voltage", "Solar Voltage", device_info)

        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_native_unit_of_measurement = "V"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = False  # Disabled by default (Venus D only)

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("pv", "pv_voltage")


class PvCurrentSensor(MarstekSensorBase):
    """Solar (PV) Current sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "pv_current", "Solar Current", device_info)

        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_native_unit_of_measurement = "A"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = False  # Disabled by default (Venus D only)

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("pv", "pv_current")


class GridPowerSensor(MarstekSensorBase):
    """Grid Power sensor (positive=exporting, negative=importing)."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "grid_power", "Grid Power", device_info)

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
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "load_power", "Load Power", device_info)

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("es", "offgrid_power")


# ============================================================================
# Energy Total Sensors
#
# These sensors are configured for Home Assistant Energy Dashboard:
# - device_class: ENERGY (identifies as energy sensor)
# - state_class: TOTAL_INCREASING (cumulative counter)
# - unit: Wh (watt-hours)
#
# Energy Dashboard Configuration:
# 1. Go to Settings > Dashboards > Energy
# 2. Configure energy sources:
#    - Solar Production: Use "Total Solar Energy"
#    - Grid Import: Use "Total Grid Import Energy"
#    - Grid Export: Use "Total Grid Export Energy"
#    - Home Consumption: Use "Total Load Energy"
# 3. The dashboard will automatically convert Wh to kWh for display
#
# Note: These are cumulative totals from device. They should never decrease.
# If a sensor resets to 0, it may cause issues in long-term statistics.
# ============================================================================


class TotalPvEnergySensor(MarstekSensorBase):
    """Total Solar Energy Generated sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "total_pv_energy", "Total Solar Energy", device_info)

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
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "total_grid_input_energy", "Total Grid Import Energy", device_info)

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
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "total_grid_output_energy", "Total Grid Export Energy", device_info)

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
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "total_load_energy", "Total Load Energy", device_info)

        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("es", "total_load_energy")


# ============================================================================
# Mode Sensors
# ============================================================================


class OperatingModeSensor(MarstekSensorBase):
    """Operating Mode sensor (Auto/AI/Manual/Passive)."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "operating_mode", "Operating Mode", device_info)

        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["Auto", "AI", "Manual", "Passive", "Unknown"]

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        mode = self._get_value("mode", "mode")
        # Ensure the value is one of the valid options
        if mode in self._attr_options:
            return mode
        return "Unknown"


# ============================================================================
# Energy Meter Sensors
# ============================================================================


class CtStateSensor(MarstekSensorBase):
    """CT (Current Transformer) Connection State sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "ct_state", "CT State", device_info)

        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["Not Connected", "Connected", "Unknown"]

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        # Get CT state from EM data (0=not connected, 1=connected)
        ct_state = self._get_value("em", "ct_state")

        if ct_state is None:
            return "Unknown"

        if ct_state == 0:
            return "Not Connected"
        elif ct_state == 1:
            return "Connected"
        else:
            return "Unknown"


class PhaseAPowerSensor(MarstekSensorBase):
    """Phase A Power sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "phase_a_power", "Phase A Power", device_info)

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("em", "a_power")


class PhaseBPowerSensor(MarstekSensorBase):
    """Phase B Power sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "phase_b_power", "Phase B Power", device_info)

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("em", "b_power")


class PhaseCPowerSensor(MarstekSensorBase):
    """Phase C Power sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "phase_c_power", "Phase C Power", device_info)

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("em", "c_power")


class TotalCtPowerSensor(MarstekSensorBase):
    """Total CT Power sensor (sum of all phases)."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "total_ct_power", "Total CT Power", device_info)

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self._get_value("em", "total_power")


# ============================================================================
# WiFi Sensors
# ============================================================================


class WifiSignalSensor(MarstekSensorBase):
    """WiFi Signal Strength sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "wifi_signal", "WiFi Signal", device_info)

        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_native_unit_of_measurement = "dBm"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = False  # Disabled by default

    @property
    def native_value(self) -> Optional[int]:
        """Return the state of the sensor."""
        return self._get_value("wifi", "rssi")


class WifiSsidSensor(MarstekSensorBase):
    """WiFi Network Name (SSID) sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "wifi_ssid", "WiFi Network", device_info)

        self._attr_entity_registry_enabled_default = False  # Disabled by default

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        return self._get_value("wifi", "ssid")


# ============================================================================
# Bluetooth Sensors
# ============================================================================


class BluetoothStateSensor(MarstekSensorBase):
    """Bluetooth Connection State sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info_dict, "bluetooth_state", "Bluetooth State", device_info)

        self._attr_entity_registry_enabled_default = False  # Disabled by default

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        return self._get_value("ble", "state")


# ============================================================================
# Diagnostic Sensors
# ============================================================================


class DiagnosticRequestCountSensor(MarstekSensorBase):
    """Total API requests sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, device_info_dict, "diagnostic_requests", "API Requests", device_info
        )
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> Optional[int]:
        """Return the state of the sensor."""
        stats = self.coordinator.get_stats()
        return stats.get("request_count")


class DiagnosticErrorRateSensor(MarstekSensorBase):
    """API error rate sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, device_info_dict, "diagnostic_error_rate", "API Error Rate", device_info
        )
        self._attr_native_unit_of_measurement = "%"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        stats = self.coordinator.get_stats()
        return stats.get("error_rate")


class DiagnosticAvgResponseTimeSensor(MarstekSensorBase):
    """Average API response time sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, device_info_dict, "diagnostic_avg_response", "Average Response Time", device_info
        )
        self._attr_native_unit_of_measurement = "s"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        stats = self.coordinator.get_stats()
        return stats.get("average_response_time")


class DiagnosticLastUpdateTimeSensor(MarstekSensorBase):
    """Last successful update timestamp sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, device_info_dict, "diagnostic_last_update", "Last Update", device_info
        )
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> Optional[datetime]:
        """Return the state of the sensor."""
        if self.coordinator.last_update_success_time:
            return self.coordinator.last_update_success_time
        return None


class DiagnosticPingTimeSensor(MarstekSensorBase):
    """Last API ping time sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, device_info_dict, "diagnostic_ping_time", "Ping Time", device_info
        )
        self._attr_native_unit_of_measurement = "ms"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        ping = self.coordinator.client.get_last_ping_time()
        return round(ping, 1) if ping is not None else None


class DeviceFirmwareSensor(MarstekSensorBase):
    """Device firmware version sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, device_info_dict, "device_firmware", "Firmware Version", device_info
        )
        self._attr_entity_registry_enabled_default = True  # Enabled by default - useful for support and compatibility checks
        self._device_info_dict = device_info_dict

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        return str(self._device_info_dict.get("ver", "Unknown"))


class DeviceModelSensor(MarstekSensorBase):
    """Device model sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info_dict: Dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, device_info_dict, "device_model", "Device Model", device_info
        )
        self._attr_entity_registry_enabled_default = True  # Enabled by default - useful for device identification
        self._device_info_dict = device_info_dict

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        return self._device_info_dict.get("device", "Unknown")
