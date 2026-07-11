"""Repair flows for Marstek Venus E."""
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


class DeviceUnreachableRepairFlow(RepairsFlow):
    """Offer to retry setup for a device that stopped responding.

    The device usually returns on its own (the coordinator deletes the issue on
    the next successful poll). This flow lets the user force a reload once they
    have re-enabled the local API or brought the device back online.
    """

    def __init__(self, entry_id: str) -> None:
        """Store the config entry to reload."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the first step of the fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Reload the config entry on confirmation."""
        if user_input is not None:
            await self.hass.config_entries.async_reload(self._entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: Optional[Dict[str, Any]],
) -> RepairsFlow:
    """Create the appropriate repair flow for an issue."""
    entry_id = (data or {}).get("entry_id")
    return DeviceUnreachableRepairFlow(entry_id)
