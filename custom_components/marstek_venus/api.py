"""Marstek Venus E API Client using UDP."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

# Default timeout for UDP responses
TIMEOUT = 10

# Minimum time between requests. The device's local API is destabilised by
# rapid polling: closely-spaced request bursts can make it reboot and lose
# persisted config (CT pairing, manual schedules, and the local-API enable
# toggle). A packet-loss probe (probe_interval.py) shows loss is flat from 1.0s
# to 2.5s, but packet loss is not the binding constraint here; firmware
# stability is. Keep this conservative and do not lower it toward the
# packet-loss floor.
MIN_REQUEST_INTERVAL = 2.5

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # Base delay in seconds for exponential backoff

# JSON-RPC parse-error code. The device intermittently answers a well-formed
# request with this error and an id of 0 (it echoes no id when it fails to
# parse the request). It is transient, so requests that hit it are retried.
PARSE_ERROR_CODE = -32700

_LOGGER = logging.getLogger(__name__)


def charge_discharge_to_wire_power(charge_w: int, discharge_w: int) -> int:
    """Map HA charge/discharge setpoints to the device's signed power value.

    On the HA side both values are non-negative: ``charge_w`` draws power into
    the battery, ``discharge_w`` pushes power out. At most one is expected to be
    non-zero; if both are set, charge wins.

    Wire convention (charge = negative, discharge = positive) is shared by both
    Manual (manual_cfg.power) and Passive (passive_cfg.power). This is INVERTED
    relative to ``bat_power`` in ES.GetStatus (where positive = charging), which
    is why the HA-facing entities use charge = positive and this function does
    the single inversion.

    Verified on VenusE 3.0 firmware 148 (2026-07-12): commanding a positive
    value exported to grid (discharge); a negative value imported (charge).
    """
    if charge_w > 0:
        return -int(charge_w)
    if discharge_w > 0:
        return int(discharge_w)
    return 0


class MarstekConnectionError(Exception):
    """Exception raised when connection to device fails."""


class MarstekApiError(Exception):
    """Exception raised when API returns an error."""

    def __init__(self, message: str, code: Optional[int] = None) -> None:
        super().__init__(message)
        self.code = code


async def discover_devices(
    timeout: float = 3.0, port: int = 30000
) -> list[Dict[str, Any]]:
    """
    Discover Marstek devices on the local network via UDP broadcast.

    Broadcasts ``Marstek.GetDevice`` to 255.255.255.255 and collects replies
    for ``timeout`` seconds.

    Args:
        timeout: How long to listen for replies after broadcasting
        port: UDP port to broadcast to (default: 30000)

    Returns:
        A list of device info dicts (the GetDevice ``result``), each with an
        added ``ip`` key for the source address the reply came from.
        Deduplicated by wifi_mac.
    """
    loop = asyncio.get_running_loop()
    responses: list[tuple[Dict[str, Any], str]] = []

    class _DiscoveryProtocol(asyncio.DatagramProtocol):
        def datagram_received(self, data: bytes, addr: tuple) -> None:
            try:
                message = json.loads(data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                return
            # Our own broadcast is echoed back on some networks; it carries no
            # "result" key, so filtering on a dict result naturally skips it.
            result = message.get("result")
            if isinstance(result, dict):
                responses.append((result, addr[0]))

    transport, _ = await loop.create_datagram_endpoint(
        _DiscoveryProtocol,
        local_addr=("0.0.0.0", 0),
        allow_broadcast=True,
    )
    try:
        payload = json.dumps(
            {"id": 0, "method": "Marstek.GetDevice", "params": {"ble_mac": "0"}}
        ).encode()
        # Send a few times; UDP broadcasts can be dropped.
        for _ in range(3):
            transport.sendto(payload, ("255.255.255.255", port))
            await asyncio.sleep(0.3)
        await asyncio.sleep(timeout)
    finally:
        transport.close()

    # Deduplicate, preferring wifi_mac as the stable identity.
    devices: Dict[str, Dict[str, Any]] = {}
    for result, ip in responses:
        device = dict(result)
        device.setdefault("ip", ip)
        key = device.get("wifi_mac") or device.get("ble_mac") or ip
        devices[key] = device
    return list(devices.values())


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
                # The device answers with id 0 both for genuine unsolicited
                # status pushes and when it fails to parse a request (it cannot
                # echo an id it never read). All device I/O is serialised, so at
                # most one request is ever in flight: an id-0 *error* is the
                # reply to that single outstanding request. Match it so the
                # caller fails fast and retries instead of waiting out the full
                # timeout.
                if (
                    request_id == 0
                    and "error" in response
                    and len(self.pending_requests) == 1
                ):
                    _, pending = self.pending_requests.popitem()
                    self._set_error(pending, response["error"])
                elif request_id == 0:
                    _LOGGER.debug(
                        "Received unsolicited message from device: %s", response
                    )
                else:
                    _LOGGER.warning(
                        "Received unexpected response with ID %s", request_id
                    )
                return

            # Check if response contains an error
            if "error" in response:
                self._set_error(future, response["error"])
            else:
                # Success! Set the result
                future.set_result(response.get("result", {}))

        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to decode JSON response: %s", err)
        except Exception as err:
            _LOGGER.error("Error processing datagram: %s", err)

    @staticmethod
    def _set_error(future: asyncio.Future, error: Dict[str, Any]) -> None:
        """Resolve a pending request future with the device's API error."""
        error_msg = f"API Error {error.get('code')}: {error.get('message')}"
        future.set_exception(MarstekApiError(error_msg, code=error.get("code")))

    def error_received(self, exc: Exception) -> None:
        """
        Called when a protocol error occurs.

        On a connected UDP socket this fires when the kernel receives an ICMP
        port-unreachable (ECONNREFUSED), i.e. the device is on the network but
        its local API is not answering. That is an expected, transient
        condition during an outage; the request layer already surfaces the
        resulting timeout, so log at DEBUG to avoid flooding the log.

        Args:
            exc: The exception that occurred
        """
        _LOGGER.debug("Protocol error: %s", exc)

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

    def __init__(self, host: str, port: int = 30000, timeout: float = TIMEOUT):
        """
        Initialize the API client.

        Args:
            host: IP address of the Marstek device
            port: UDP port number (default: 30000)
            timeout: Default response timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.protocol: Optional[MarstekProtocol] = None
        self._request_id = 0  # Counter for generating unique request IDs
        self._last_request_time = 0.0  # Track last request time for rate limiting
        # Serialize device I/O. The device needs >=2s between requests and does
        # not handle concurrent in-flight requests, so a poll and a control
        # command (e.g. a Number setpoint) must not overlap. Held across the
        # whole send+response so only one request is on the wire at a time.
        self._request_lock = asyncio.Lock()

        # Diagnostic tracking
        self._request_stats: Dict[str, Dict[str, Any]] = {}
        self._consecutive_failures = 0
        self._last_successful_request = None

    async def connect(self) -> None:
        """
        Establish UDP connection to the device.

        Raises:
            MarstekConnectionError: If connection fails
        """
        try:
            # Create a UDP endpoint
            # This returns (transport, protocol)
            loop = asyncio.get_running_loop()
            _, self.protocol = await loop.create_datagram_endpoint(
                MarstekProtocol, remote_addr=(self.host, self.port)
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

        The device appears to treat request IDs as 16-bit values, so the
        counter wraps at 0xFFFF to keep request/response matching stable on
        long-running polls. 0 is skipped because the device uses it for
        unsolicited status messages (see MarstekProtocol.datagram_received),
        so IDs cycle through 1..0xFFFF.

        Returns:
            A unique integer ID in the range 1..0xFFFF
        """
        self._request_id = (self._request_id % 0xFFFF) + 1
        return self._request_id

    def _update_stats(
        self, method: str, success: bool, duration: float, error: Optional[str] = None
    ) -> None:
        """Update diagnostic statistics for a method."""
        if method not in self._request_stats:
            self._request_stats[method] = {
                "total_calls": 0,
                "success_count": 0,
                "failure_count": 0,
                "timeout_count": 0,
                "api_error_count": 0,
                "total_duration": 0.0,
                "last_error": None,
                "last_success": None,
            }

        stats = self._request_stats[method]
        stats["total_calls"] += 1
        stats["total_duration"] += duration

        if success:
            stats["success_count"] += 1
            stats["last_success"] = time.time()
            self._consecutive_failures = 0
            self._last_successful_request = time.time()
        else:
            stats["failure_count"] += 1
            stats["last_error"] = error
            self._consecutive_failures += 1

            if error and "timeout" in error.lower():
                stats["timeout_count"] += 1
            elif error and "API Error" in error:
                stats["api_error_count"] += 1

    def get_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostic information about API calls."""
        diagnostics = {
            "consecutive_failures": self._consecutive_failures,
            "last_successful_request": self._last_successful_request,
            "methods": {},
        }

        for method, stats in self._request_stats.items():
            avg_duration = 0.0
            if stats["total_calls"] > 0:
                avg_duration = stats["total_duration"] / stats["total_calls"]

            success_rate = 0.0
            if stats["total_calls"] > 0:
                success_rate = (stats["success_count"] / stats["total_calls"]) * 100

            diagnostics["methods"][method] = {
                "total_calls": stats["total_calls"],
                "success_rate": round(success_rate, 1),
                "timeout_count": stats["timeout_count"],
                "api_error_count": stats["api_error_count"],
                "avg_duration_ms": round(avg_duration * 1000, 1),
                "last_error": stats["last_error"],
            }

        return diagnostics

    async def _send_command_once(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = TIMEOUT,
    ) -> Dict[str, Any]:
        """
        Send a command to the device once (no retry).

        Args:
            method: The API method name
            params: Optional parameters dictionary
            timeout: Response timeout in seconds

        Returns:
            The result dictionary from the device response

        Raises:
            MarstekConnectionError: If not connected
            MarstekApiError: If device returns an error
            asyncio.TimeoutError: If response takes too long
        """
        if not self.protocol or not self.protocol.transport:
            raise MarstekConnectionError("Not connected to device")

        # Serialize the whole exchange so concurrent callers (a poll and a
        # control command) cannot interleave rate-limit bookkeeping or overlap
        # in-flight requests on the single-request-at-a-time device.
        async with self._request_lock:
            # Rate limiting: Venus E 3 requires 2+ seconds between requests
            current_time = time.monotonic()
            elapsed = current_time - self._last_request_time
            if elapsed < MIN_REQUEST_INTERVAL:
                sleep_time = MIN_REQUEST_INTERVAL - elapsed
                _LOGGER.debug(
                    "Rate limiting: sleeping %.2fs before next request", sleep_time
                )
                await asyncio.sleep(sleep_time)

            # Update last request time
            self._last_request_time = time.monotonic()

            # Generate unique request ID
            request_id = self._get_next_id()

            # Build the JSON-RPC request
            request = {"id": request_id, "method": method, "params": params or {}}

            # Create a Future to wait for the response
            future = asyncio.get_running_loop().create_future()
            self.protocol.pending_requests[request_id] = future

            try:
                # Send the request
                data = json.dumps(request).encode()
                self.protocol.transport.sendto(data)
                _LOGGER.debug("Sent request: %s", request)

                # Wait for response with timeout
                result = await asyncio.wait_for(future, timeout=timeout)
                return result

            finally:
                # Always clean up pending request
                self.protocol.pending_requests.pop(request_id, None)

    async def send_command(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        retries: int = MAX_RETRIES,
    ) -> Dict[str, Any]:
        """
        Send a command to the device and wait for response with retry logic.

        This is the core method that all other API methods use.
        It handles:
        - Creating the JSON-RPC request
        - Sending it over UDP
        - Waiting for the response with timeout
        - Automatic retry with exponential backoff on timeout
        - Diagnostic tracking

        Args:
            method: The API method name (e.g., "Marstek.GetDevice")
            params: Optional parameters dictionary
            timeout: Response timeout in seconds
            retries: Number of retry attempts (default: MAX_RETRIES)

        Returns:
            The result dictionary from the device response

        Raises:
            MarstekConnectionError: If not connected or connection fails
            MarstekApiError: If device returns an error
            asyncio.TimeoutError: If all retry attempts timeout
        """
        if timeout is None:
            timeout = self.timeout

        request_start = time.monotonic()
        last_error: Optional[Exception] = None

        for attempt in range(retries + 1):
            attempt_start = time.monotonic()

            try:
                result = await self._send_command_once(method, params, timeout)

                # Success - update stats and return
                duration = time.monotonic() - request_start
                self._update_stats(method, success=True, duration=duration)

                # Calculate ping time
                ping_time = (time.monotonic() - attempt_start) * 1000
                self._last_ping_time = ping_time

                if attempt > 0:
                    _LOGGER.info(
                        "Request %s succeeded on attempt %d/%d",
                        method,
                        attempt + 1,
                        retries + 1,
                    )

                return result

            except asyncio.TimeoutError as err:
                last_error = err
                if attempt < retries:
                    # Calculate exponential backoff delay
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    _LOGGER.debug(
                        "Request %s timed out (attempt %d/%d), retrying in %.1fs",
                        method,
                        attempt + 1,
                        retries + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final failure is surfaced to the coordinator, which logs
                    # it once; keep the retry mechanics at DEBUG.
                    _LOGGER.debug(
                        "Request %s failed after %d attempts due to timeout",
                        method,
                        retries + 1,
                    )

            except MarstekApiError as err:
                # A -32700 parse error is the device spuriously rejecting a
                # well-formed request; it is transient, so retry like a timeout.
                # Other API errors (method not found, invalid params) are
                # deterministic and must not be retried.
                if err.code == PARSE_ERROR_CODE and attempt < retries:
                    last_error = err
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    _LOGGER.debug(
                        "Request %s rejected with parse error (attempt %d/%d), "
                        "retrying in %.1fs",
                        method,
                        attempt + 1,
                        retries + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                # Deterministic API error, or parse error with retries exhausted.
                duration = time.monotonic() - request_start
                self._update_stats(
                    method, success=False, duration=duration, error=str(err)
                )
                self._last_ping_time = None
                _LOGGER.warning("Request %s failed with API error: %s", method, err)
                raise

            except MarstekConnectionError as err:
                # Connection errors might be recoverable with retry
                last_error = err
                if attempt < retries:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    _LOGGER.debug(
                        "Request %s connection error (attempt %d/%d): %s, retrying in %.1fs",
                        method,
                        attempt + 1,
                        retries + 1,
                        err,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final failure is surfaced to the coordinator, which logs
                    # it once; keep the retry mechanics at DEBUG.
                    _LOGGER.debug(
                        "Request %s failed after %d attempts due to connection error: %s",
                        method,
                        retries + 1,
                        err,
                    )

        # All retries exhausted
        duration = time.monotonic() - request_start
        error_msg = str(last_error) if last_error else "Unknown error"
        self._update_stats(method, success=False, duration=duration, error=error_msg)
        self._last_ping_time = None

        if isinstance(last_error, asyncio.TimeoutError):
            raise asyncio.TimeoutError(
                f"Request {method} timed out after {retries + 1} attempts"
            ) from last_error
        elif isinstance(last_error, MarstekConnectionError):
            raise last_error
        else:
            raise MarstekConnectionError(
                f"Request {method} failed after {retries + 1} attempts: {error_msg}"
            ) from last_error

    def get_last_ping_time(self) -> Optional[float]:
        """Get last successful request ping time in milliseconds."""
        return getattr(self, "_last_ping_time", None)

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
        params = {"id": 0, "config": {"mode": mode, **config}}
        result = await self.send_command("ES.SetMode", params)
        # Result should contain set_result: true/false
        return result.get("set_result", False)
