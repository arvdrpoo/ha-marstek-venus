"""Config flow for Marstek Venus E integration."""
import asyncio
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .api import MarstekApiClient, MarstekConnectionError, MarstekApiError
from .const import (
    CONF_HOST,
    CONF_PORT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


# Schema for user input form
# This defines what fields appear in the configuration UI
USER_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
})


async def validate_connection(
    hass: HomeAssistant, host: str, port: int
) -> Dict[str, Any]:
    """
    Validate that we can connect to the device.

    This function attempts to connect to the device and retrieve
    basic information to verify the connection works.

    Args:
        hass: Home Assistant instance
        host: Device IP address
        port: UDP port number

    Returns:
        Dictionary with device information

    Raises:
        MarstekConnectionError: If connection fails
        MarstekApiError: If API call fails
        asyncio.TimeoutError: If connection times out
    """
    # Create API client
    client = MarstekApiClient(host, port)

    try:
        # Connect to device
        await client.connect()

        # Try to get device information
        # This validates that the device is reachable and responding
        device_info = await client.get_device_info()

        return device_info

    finally:
        # Always close the connection
        await client.close()


class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handle a config flow for Marstek Venus E.

    This class manages the UI flow when users add the integration.
    It displays a form, validates the input, and creates a config entry.
    """

    VERSION = 1  # Config entry version

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """
        Handle the initial step when user adds integration.

        This method is called twice:
        1. First time (user_input=None): Show the form
        2. Second time (user_input=filled): Validate and create entry

        Args:
            user_input: None on first call, filled dict on form submission

        Returns:
            FlowResult that either shows form or creates config entry
        """
        errors: Dict[str, str] = {}

        if user_input is not None:
            # User submitted the form, validate the input
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            try:
                # Attempt to connect and get device info
                device_info = await validate_connection(self.hass, host, port)

                # Extract device identifiers
                # Use WiFi MAC as unique identifier
                wifi_mac = device_info.get("wifi_mac", "")
                device_model = device_info.get("device", "VenusE")

                # Check if this device is already configured
                # This prevents duplicate entries for the same device
                await self.async_set_unique_id(wifi_mac)
                self._abort_if_unique_id_configured()

                # Success! Create the config entry
                # The title shown in UI will be the device name
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, f"{device_model} {wifi_mac[-4:]}"),
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                    },
                )

            except asyncio.TimeoutError:
                # Device didn't respond in time
                errors["base"] = "timeout"
                _LOGGER.warning("Timeout connecting to %s:%s", host, port)

            except (MarstekConnectionError, MarstekApiError) as err:
                # Failed to connect or API error
                errors["base"] = "cannot_connect"
                _LOGGER.error("Failed to connect to %s:%s: %s", host, port, err)

            except Exception as err:  # pylint: disable=broad-except
                # Unexpected error
                errors["base"] = "unknown"
                _LOGGER.exception("Unexpected error: %s", err)

        # Show the configuration form
        # Either first time, or again if there were errors
        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )
