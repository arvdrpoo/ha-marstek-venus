"""Marstek Venus E API Client using UDP."""
import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

# Default timeout for UDP responses
TIMEOUT = 10

# Minimum time between requests (Venus E 3 requires 2+ seconds)
MIN_REQUEST_INTERVAL = 2.5

_LOGGER = logging.getLogger(__name__)


class MarstekConnectionError(Exception):
    """Exception raised when connection to device fails."""


class MarstekApiError(Exception):
    """Exception raised when API returns an error."""


class MarstekProtocol(asyncio.DatagramProtocol):
    """
    UDP Protocol handler for Marstek device communication.

    This class handles the low-level UDP communication using asyncio's
    DatagramProtocol. It receives responses from the device and matches
    them to pending requests.
    """

    def __init__(self):
        """Initialize the protocol."""
        self.transport: Optional[asyncio.DatagramTransport] = None
        # Dictionary to store pending requests: {request_id: Future}
        self.pending_requests: Dict[int, asyncio.Future] = {}

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """
        Called when the UDP socket is created.

        Args:
            transport: The transport object for sending data
        """
        self.transport = transport
        _LOGGER.debug("UDP connection established")

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        """
        Called when a UDP datagram is received from the device.

        This method parses the JSON response and completes the
        corresponding Future object so the caller can receive the result.

        Args:
            data: The raw bytes received
            addr: The (host, port) tuple of the sender
        """
        try:
            # Parse the JSON response
            response = json.loads(data.decode())
            _LOGGER.debug("Received response: %s", response)

            # Extract the request ID from the response
            request_id = response.get("id")
            if request_id is None:
                _LOGGER.warning("Received response without ID: %s", response)
                return

            # Find the pending request matching this ID
            future = self.pending_requests.pop(request_id, None)
            if future is None:
                # ID 0 is often used for unsolicited status updates from the device
                # Log at debug level to avoid cluttering logs
                if request_id == 0:
                    _LOGGER.debug("Received unsolicited message from device: %s", response)
                else:
                    _LOGGER.warning("Received unexpected response with ID %s", request_id)
                return

            # Check if response contains an error
            if "error" in response:
                error = response["error"]
                error_msg = f"API Error {error.get('code')}: {error.get('message')}"
                future.set_exception(MarstekApiError(error_msg))
            else:
                # Success! Set the result
                future.set_result(response.get("result", {}))

        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to decode JSON response: %s", err)
        except Exception as err:
            _LOGGER.error("Error processing datagram: %s", err)

    def error_received(self, exc: Exception) -> None:
        """
        Called when a protocol error occurs.

        Args:
            exc: The exception that occurred
        """
        _LOGGER.error("Protocol error: %s", exc)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """
        Called when the connection is closed.

        Args:
            exc: Exception if connection was closed due to error
        """
        if exc:
            _LOGGER.error("Connection lost: %s", exc)
        else:
            _LOGGER.debug("Connection closed")


class MarstekApiClient:
    """
    API client for Marstek Venus E device.

    This client provides high-level async methods for interacting with
    the Marstek device over UDP using a JSON-RPC style protocol.

    Usage:
        client = MarstekApiClient("192.168.1.100", 30000)
        await client.connect()
        try:
            device_info = await client.get_device_info()
            battery_status = await client.get_bat_status()
        finally:
            await client.close()
    """

    def __init__(self, host: str, port: int = 30000):
        """
        Initialize the API client.

        Args:
            host: IP address of the Marstek device
            port: UDP port number (default: 30000)
        """
        self.host = host
        self.port = port
        self.protocol: Optional[MarstekProtocol] = None
        self._request_id = 0  # Counter for generating unique request IDs
        self._last_request_time = 0.0  # Track last request time for rate limiting

    async def connect(self) -> None:
        """
        Establish UDP connection to the device.

        Raises:
            MarstekConnectionError: If connection fails
        """
        try:
            # Create a UDP endpoint
            # This returns (transport, protocol)
            loop = asyncio.get_event_loop()
            _, self.protocol = await loop.create_datagram_endpoint(
                MarstekProtocol,
                remote_addr=(self.host, self.port)
            )
            _LOGGER.info("Connected to Marstek device at %s:%s", self.host, self.port)
        except Exception as err:
            raise MarstekConnectionError(f"Failed to connect: {err}") from err

    async def close(self) -> None:
        """Close the UDP connection."""
        if self.protocol and self.protocol.transport:
            self.protocol.transport.close()
            _LOGGER.info("Disconnected from Marstek device")

    def _get_next_id(self) -> int:
        """
        Generate a unique request ID.

        Returns:
            A unique integer ID
        """
        self._request_id += 1
        return self._request_id

    async def send_command(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = TIMEOUT
    ) -> Dict[str, Any]:
        """
        Send a command to the device and wait for response.

        This is the core method that all other API methods use.
        It handles:
        - Creating the JSON-RPC request
        - Sending it over UDP
        - Waiting for the response with timeout
        - Error handling

        Args:
            method: The API method name (e.g., "Marstek.GetDevice")
            params: Optional parameters dictionary
            timeout: Response timeout in seconds

        Returns:
            The result dictionary from the device response

        Raises:
            MarstekConnectionError: If not connected or connection fails
            MarstekApiError: If device returns an error
            asyncio.TimeoutError: If response takes too long
        """
        if not self.protocol or not self.protocol.transport:
            raise MarstekConnectionError("Not connected to device")

        # Rate limiting: Venus E 3 requires 2+ seconds between requests
        current_time = time.monotonic()
        elapsed = current_time - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - elapsed
            _LOGGER.debug("Rate limiting: sleeping %.2fs before next request", sleep_time)
            await asyncio.sleep(sleep_time)

        # Update last request time
        self._last_request_time = time.monotonic()

        # Track request timing for diagnostics
        request_start = time.monotonic()

        # Generate unique request ID
        request_id = self._get_next_id()

        # Build the JSON-RPC request
        request = {
            "id": request_id,
            "method": method,
            "params": params or {}
        }

        # Create a Future to wait for the response
        future = asyncio.get_event_loop().create_future()
        self.protocol.pending_requests[request_id] = future

        try:
            # Send the request
            data = json.dumps(request).encode()
            self.protocol.transport.sendto(data)
            _LOGGER.debug("Sent request: %s", request)

            # Wait for response with timeout
            result = await asyncio.wait_for(future, timeout=timeout)

            # Calculate ping time
            ping_time = (time.monotonic() - request_start) * 1000  # milliseconds
            self._last_ping_time = ping_time

            return result

        except asyncio.TimeoutError:
            # Clean up pending request on timeout
            self._last_ping_time = None
            self.protocol.pending_requests.pop(request_id, None)
            raise
        except Exception:
            # Clean up pending request on any error
            self._last_ping_time = None
            self.protocol.pending_requests.pop(request_id, None)
            raise

    def get_last_ping_time(self) -> Optional[float]:
        """Get last successful request ping time in milliseconds."""
        return getattr(self, '_last_ping_time', None)

    async def get_device_info(self) -> Dict[str, Any]:
        """
        Get basic device information.

        Calls: Marstek.GetDevice

        Returns:
            Dictionary with device info including:
            - device: Model name (e.g., "VenusE")
            - ver: Firmware version
            - ble_mac: Bluetooth MAC address
            - wifi_mac: WiFi MAC address
            - wifi_name: Connected WiFi network name
            - ip: Device IP address

        Raises:
            MarstekConnectionError: If not connected
            MarstekApiError: If device returns an error
        """
        return await self.send_command("Marstek.GetDevice", {"ble_mac": "0"})

    async def get_es_status(self) -> Dict[str, Any]:
        """
        Get energy system status.

        Calls: ES.GetStatus

        Returns:
            Dictionary with energy data including:
            - id: ID of Instance (number or null)
            - bat_soc: Total battery SOC, [%] (number or null)
            - bat_cap: Total battery capacity, [Wh] (number or null)
            - pv_power: Solar charging power, [W] (number or null)
            - ongrid_power: Grid-tied power, [W] (number or null)
            - offgrid_power: Off-grid power, [W] (number or null)
            - bat_power: Battery power, [W] (number or null)
            - total_pv_energy: Total solar energy generated, [Wh] (number or null)
            - total_grid_output_energy: Total grid output energy, [Wh] (number or null)
            - total_grid_input_energy: Total grid input energy, [Wh] (number or null)
            - total_load_energy: Total load (or off-grid) energy consumed, [Wh] (number or null)
        """
        return await self.send_command("ES.GetStatus", {"id": 0})

    async def get_bat_status(self) -> Dict[str, Any]:
        """
        Get battery status.

        Calls: Bat.GetStatus

        Returns:
            Dictionary with battery data including:
            - id: ID of Instance (number)
            - soc: State of charge, [%] (string)
            - charg_flag: Charging permission flag (boolean)
            - dischrg_flag: Discharge permission flag (boolean)
            - bat_temp: Battery temperature, [°C] (number or null)
            - bat_capacity: Battery remaining capacity, [Wh] (number or null)
            - rated_capacity: Battery rated capacity, [Wh] (number or null)
        """
        return await self.send_command("Bat.GetStatus", {"id": 0})

    async def get_pv_status(self) -> Dict[str, Any]:
        """
        Get photovoltaic (solar) status.

        Calls: PV.GetStatus

        Returns:
            Dictionary with PV data including:
            - id: ID of Instance (number)
            - pv_power: Photovoltaic charging power, [W] (number)
            - pv_voltage: Photovoltaic charging voltage, [V] (number)
            - pv_current: Photovoltaic charging current, [A] (number)

        Note:
            Venus C/E models don't have PV component. This will fail on Venus E 3.
            Venus D models support this endpoint.
        """
        return await self.send_command("PV.GetStatus", {"id": 0})

    async def get_em_status(self) -> Dict[str, Any]:
        """
        Get energy meter (CT sensor) status.

        Calls: EM.GetStatus

        Returns:
            Dictionary with CT data including:
            - id: ID of Instance (number or null)
            - ct_state: 0=not connected, 1=connected (number or null)
            - a_power: Phase A power, [W] (number or null)
            - b_power: Phase B power, [W] (number or null)
            - c_power: Phase C power, [W] (number or null)
            - total_power: Total power, [W] (number or null)
        """
        return await self.send_command("EM.GetStatus", {"id": 0})

    async def get_wifi_status(self) -> Dict[str, Any]:
        """
        Get WiFi connection status.

        Calls: Wifi.GetStatus

        Returns:
            Dictionary with WiFi data including:
            - id: ID of Instance (number)
            - wifi_mac: WiFi MAC address (string)
            - ssid: WiFi network name (string or null)
            - rssi: WiFi signal strength in dBm (number)
            - sta_ip: Device IP address (string or null)
            - sta_gate: Gateway address (string or null)
            - sta_mask: Subnet mask (string or null)
            - sta_dns: DNS server address (string or null)
        """
        return await self.send_command("Wifi.GetStatus", {"id": 0})

    async def get_ble_status(self) -> Dict[str, Any]:
        """
        Get Bluetooth connection status.

        Calls: BLE.GetStatus

        Returns:
            Dictionary with Bluetooth data including:
            - id: ID of Instance (number)
            - state: Bluetooth state (string)
            - ble_mac: Bluetooth MAC address (string)
        """
        return await self.send_command("BLE.GetStatus", {"id": 0})

    async def get_mode(self) -> Dict[str, Any]:
        """
        Get current operating mode.

        Calls: ES.GetMode

        Returns:
            Dictionary with mode info including:
            - id: ID of Instance (number or null)
            - mode: Current mode - "Auto", "AI", "Manual", or "Passive" (string or null)
            - ongrid_power: Grid-tied power, [W] (number or null)
            - offgrid_power: Off-grid power, [W] (number or null)
            - bat_soc: SOC, [%] (number or null)
        """
        return await self.send_command("ES.GetMode", {"id": 0})

    async def set_mode(self, mode: str, config: Dict[str, Any]) -> bool:
        """
        Set the operating mode.

        Calls: ES.SetMode

        Args:
            mode: The mode to set ("Auto", "AI", "Manual", or "Passive")
            config: Mode-specific configuration dictionary:
                - Auto mode: {"auto_cfg": {"enable": 1}}
                - AI mode: {"ai_cfg": {"enable": 1}}
                - Manual mode: {"manual_cfg": {
                    "time_num": 0-9,        # Time period number (Venus C/E supports 0-9)
                    "start_time": "hh:mm",  # Start time
                    "end_time": "hh:mm",    # End time
                    "week_set": 0-127,      # Week bitmap (bit 0=Mon, 127=all days)
                    "power": number,        # Setting power [W]
                    "enable": 0 or 1        # ON: 1, OFF: 0
                  }}
                - Passive mode: {"passive_cfg": {
                    "power": number,        # Setting power [W]
                    "cd_time": number       # Power countdown [seconds]
                  }}

        Returns:
            True if successful, False otherwise

        Raises:
            MarstekApiError: If mode setting fails

        Examples:
            # Set Auto mode
            await client.set_mode("Auto", {"auto_cfg": {"enable": 1}})

            # Set AI mode
            await client.set_mode("AI", {"ai_cfg": {"enable": 1}})

            # Set Manual mode - 100W from 08:30 to 20:30, Monday-Friday
            await client.set_mode("Manual", {
                "manual_cfg": {
                    "time_num": 0,
                    "start_time": "08:30",
                    "end_time": "20:30",
                    "week_set": 31,  # Mon-Fri (binary: 0011111)
                    "power": 100,
                    "enable": 1
                }
            })

            # Set Passive mode - 100W for 300 seconds
            await client.set_mode("Passive", {
                "passive_cfg": {"power": 100, "cd_time": 300}
            })
        """
        params = {
            "id": 0,
            "config": {
                "mode": mode,
                **config
            }
        }
        result = await self.send_command("ES.SetMode", params)
        # Result should contain set_result: true/false
        return result.get("set_result", False)
