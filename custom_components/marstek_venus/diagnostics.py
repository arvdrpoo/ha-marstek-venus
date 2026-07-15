"""Diagnostics support for Marstek Venus E."""
from typing import Any, Dict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, DOMAIN
from .coordinator import MarstekDataUpdateCoordinator

# Identifiers and network details that could identify the device or its owner.
TO_REDACT = {
    CONF_HOST,
    "wifi_mac",
    "ble_mac",
    "wifi_name",
    "ssid",
    "ip",
    "sta_ip",
    "sta_gate",
    "sta_mask",
    "sta_dns",
    "unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: MarstekDataUpdateCoordinator = data["coordinator"]

    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "device_info": async_redact_data(dict(data.get("device_info", {})), TO_REDACT),
        "stats": coordinator.get_stats(),
        "passive_control": {
            "charge_power": coordinator.passive_charge_power,
            "discharge_power": coordinator.passive_discharge_power,
            "countdown": coordinator.passive_countdown,
        },
        "schedule": {
            "auto_reassert": coordinator.auto_reassert,
            "slots": coordinator.schedule,
        },
        "coordinator_data": async_redact_data(
            coordinator.data if isinstance(coordinator.data, dict) else {}, TO_REDACT
        ),
    }
