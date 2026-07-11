"""Config flow for Marstek Venus E integration."""
import asyncio
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .api import (
    MarstekApiClient,
    MarstekApiError,
    MarstekConnectionError,
    discover_devices,
)
from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_ENABLE_WIFI_SENSORS,
    CONF_ENABLE_BLE_SENSORS,
    CONF_ENABLE_PV_SENSORS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_ENABLE_WIFI_SENSORS,
    DEFAULT_ENABLE_BLE_SENSORS,
    DEFAULT_ENABLE_PV_SENSORS,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_TIMEOUT,
    MAX_TIMEOUT,
    TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


# Schema for manual IP entry
MANUAL_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
})

# Sentinel value in the discovery picker meaning "enter an IP manually"
MANUAL_SENTINEL = "__manual__"


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

    Supports three entry paths:
    - User-initiated: broadcasts for devices and offers a picker, falling back
      to manual IP entry.
    - Manual: direct IP/port entry.
    - DHCP: HA surfaces the device automatically from its MAC.

    All paths key the config entry on the normalised MAC (format_mac) so the
    same physical device is recognised regardless of how it was found.
    """

    VERSION = 2  # Bumped for MAC-normalised unique IDs (see async_migrate_entry)

    def __init__(self) -> None:
        """Initialize per-flow discovery state."""
        self._discovered_devices: Dict[str, Dict[str, Any]] = {}
        self._discovered_host: Optional[str] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step: discover devices and offer a picker."""
        # First visit: broadcast and build the picker.
        if user_input is None:
            try:
                devices = await discover_devices()
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.debug("Device discovery failed: %s", err)
                devices = []

            configured = self._async_current_ids()
            self._discovered_devices = {}
            for device in devices:
                mac = device.get("wifi_mac")
                if mac and format_mac(mac) in configured:
                    continue  # already set up
                ip = device.get("ip")
                if ip:
                    self._discovered_devices[ip] = device

            # Nothing found: go straight to manual entry.
            if not self._discovered_devices:
                return await self.async_step_manual()

            options = {
                ip: f"{device.get('device', 'Marstek')} ({ip})"
                for ip, device in self._discovered_devices.items()
            }
            options[MANUAL_SENTINEL] = "Enter IP address manually"

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_HOST): vol.In(options)}),
            )

        # A choice was made in the picker.
        selected = user_input[CONF_HOST]
        if selected == MANUAL_SENTINEL:
            return await self.async_step_manual()

        device = self._discovered_devices.get(selected, {})
        wifi_mac = device.get("wifi_mac", "")
        device_model = device.get("device", "VenusE")

        if wifi_mac:
            await self.async_set_unique_id(format_mac(wifi_mac))
            self._abort_if_unique_id_configured()

        errors: Dict[str, str] = {}
        try:
            await validate_connection(self.hass, selected, DEFAULT_PORT)
        except asyncio.TimeoutError:
            errors["base"] = "timeout"
        except (MarstekConnectionError, MarstekApiError):
            errors["base"] = "cannot_connect"
        else:
            suffix = wifi_mac[-4:] if wifi_mac else selected
            return self.async_create_entry(
                title=f"{device_model} {suffix}",
                data={CONF_HOST: selected, CONF_PORT: DEFAULT_PORT},
            )

        # Validation failed: fall back to manual entry showing the error.
        return await self.async_step_manual(errors=errors)

    async def async_step_manual(
        self,
        user_input: Optional[Dict[str, Any]] = None,
        errors: Optional[Dict[str, str]] = None,
    ) -> FlowResult:
        """Handle manual IP entry."""
        errors = errors or {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            try:
                device_info = await validate_connection(self.hass, host, port)
                wifi_mac = device_info.get("wifi_mac", "")
                device_model = device_info.get("device", "VenusE")

                if wifi_mac:
                    await self.async_set_unique_id(format_mac(wifi_mac))
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, f"{device_model} {wifi_mac[-4:]}"),
                    data={CONF_HOST: host, CONF_PORT: port},
                )

            except asyncio.TimeoutError:
                errors["base"] = "timeout"
                _LOGGER.warning("Timeout connecting to %s:%s", host, port)

            except (MarstekConnectionError, MarstekApiError) as err:
                errors["base"] = "cannot_connect"
                _LOGGER.error("Failed to connect to %s:%s: %s", host, port, err)

            except Exception as err:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception("Unexpected error: %s", err)

        return self.async_show_form(
            step_id="manual",
            data_schema=MANUAL_SCHEMA,
            errors=errors,
        )

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> FlowResult:
        """Handle a device surfaced by HA's DHCP discovery.

        The device's DHCP (layer-2) MAC does not match the wifi_mac the API
        reports, so the L2 MAC is only used to trigger and coalesce the flow.
        The real identity (wifi_mac) is fetched by connecting in the confirm
        step, keeping the entry identity consistent with the other paths.
        """
        host = discovery_info.ip

        # Already set up at this IP: nothing to do.
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == host:
                return self.async_abort(reason="already_configured")

        # Use the L2 MAC only to coalesce duplicate DHCP events for this
        # device while the flow is pending (aborts as already_in_progress).
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))

        self._discovered_host = host
        self.context["title_placeholders"] = {"name": f"Marstek Venus ({host})"}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Ask the user to confirm a DHCP-discovered device before adding it."""
        errors: Dict[str, str] = {}
        host = self._discovered_host

        if user_input is not None:
            try:
                device_info = await validate_connection(self.hass, host, DEFAULT_PORT)
            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except (MarstekConnectionError, MarstekApiError):
                errors["base"] = "cannot_connect"
            else:
                # Identify by the API wifi_mac (consistent with all paths).
                # If this device already exists, adopt the new IP and abort.
                wifi_mac = device_info.get("wifi_mac", "")
                if wifi_mac:
                    await self.async_set_unique_id(
                        format_mac(wifi_mac), raise_on_progress=False
                    )
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})

                device_model = device_info.get("device", "VenusE")
                return self.async_create_entry(
                    title=f"{device_model} ({host})",
                    data={CONF_HOST: host, CONF_PORT: DEFAULT_PORT},
                )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": host},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "OptionsFlowHandler":
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Marstek Venus integration."""

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Validate scan interval
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            if not (MIN_SCAN_INTERVAL <= scan_interval <= MAX_SCAN_INTERVAL):
                errors[CONF_SCAN_INTERVAL] = "invalid_scan_interval"

            # Validate timeout
            timeout = user_input.get(CONF_TIMEOUT, TIMEOUT)
            if not (MIN_TIMEOUT <= timeout <= MAX_TIMEOUT):
                errors[CONF_TIMEOUT] = "invalid_timeout"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        # Prefill from the just-submitted values when re-showing after an
        # error, otherwise from the currently stored options.
        values = user_input if user_input is not None else self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=values.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="seconds",
                    )
                ),
                vol.Optional(
                    CONF_TIMEOUT,
                    default=values.get(CONF_TIMEOUT, TIMEOUT)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_TIMEOUT,
                        max=MAX_TIMEOUT,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="seconds",
                    )
                ),
                vol.Optional(
                    CONF_ENABLE_WIFI_SENSORS,
                    default=values.get(CONF_ENABLE_WIFI_SENSORS, DEFAULT_ENABLE_WIFI_SENSORS)
                ): cv.boolean,
                vol.Optional(
                    CONF_ENABLE_BLE_SENSORS,
                    default=values.get(CONF_ENABLE_BLE_SENSORS, DEFAULT_ENABLE_BLE_SENSORS)
                ): cv.boolean,
                vol.Optional(
                    CONF_ENABLE_PV_SENSORS,
                    default=values.get(CONF_ENABLE_PV_SENSORS, DEFAULT_ENABLE_PV_SENSORS)
                ): cv.boolean,
            }),
            errors=errors,
        )
