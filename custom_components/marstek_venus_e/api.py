"""Marstek Venus E API Client using UDP."""
import asyncio
import json
import logging
from typing import Any, Dict, Optional

# Default timeout for UDP responses
TIMEOUT = 10

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
            return result

        except asyncio.TimeoutError:
            # Clean up pending request on timeout
            self.protocol.pending_requests.pop(request_id, None)
            raise
        except Exception:
            # Clean up pending request on any error
            self.protocol.pending_requests.pop(request_id, None)
            raise

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
            - bat_soc: Battery state of charge (%)
            - bat_cap: Battery capacity (Wh)
            - pv_power: Solar power (W)
            - ongrid_power: Grid power (W, positive=export)
            - offgrid_power: Load power (W)
            - bat_power: Battery power (W, positive=charging)
            - total_pv_energy: Total solar energy (Wh)
            - total_grid_output_energy: Total grid export (Wh)
            - total_grid_input_energy: Total grid import (Wh)
            - total_load_energy: Total load consumption (Wh)
        """
        return await self.send_command("ES.GetStatus", {"id": 0})

    async def get_bat_status(self) -> Dict[str, Any]:
        """
        Get battery status.

        Calls: Bat.GetStatus

        Returns:
            Dictionary with battery data including:
            - soc: State of charge (%)
            - charg_flag: Charging enabled (bool)
            - dischrg_flag: Discharging enabled (bool)
            - bat_temp: Temperature (°C)
            - bat_capacity: Remaining capacity (Wh)
            - rated_capacity: Rated capacity (Wh)
        """
        return await self.send_command("Bat.GetStatus", {"id": 0})

    async def get_em_status(self) -> Dict[str, Any]:
        """
        Get energy meter (CT sensor) status.

        Calls: EM.GetStatus

        Returns:
            Dictionary with CT data including:
            - ct_state: 0=not connected, 1=connected
            - a_power: Phase A power (W)
            - b_power: Phase B power (W)
            - c_power: Phase C power (W)
            - total_power: Total power (W)
        """
        return await self.send_command("EM.GetStatus", {"id": 0})

    async def get_mode(self) -> Dict[str, Any]:
        """
        Get current operating mode.

        Calls: ES.GetMode

        Returns:
            Dictionary with mode info including:
            - mode: Current mode ("Auto", "AI", "Manual", or "Passive")
            - ongrid_power: Grid power (W)
            - offgrid_power: Load power (W)
            - bat_soc: Battery SOC (%)
        """
        return await self.send_command("ES.GetMode", {"id": 0})

    async def set_mode(self, mode: str, config: Dict[str, Any]) -> bool:
        """
        Set the operating mode.

        Calls: ES.SetMode

        Args:
            mode: The mode to set ("Auto", "AI", "Manual", or "Passive")
            config: Mode-specific configuration dictionary

        Returns:
            True if successful

        Raises:
            MarstekApiError: If mode setting fails

        Example:
            # Set Auto mode
            await client.set_mode("Auto", {"auto_cfg": {"enable": 1}})

            # Set Passive mode with 100W for 300 seconds
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
