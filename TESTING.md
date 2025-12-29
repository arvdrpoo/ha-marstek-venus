# Testing Guide

This guide covers different ways to test the Marstek Venus E integration.

## Quick Test: Standalone API Client (Recommended First)

Test the UDP API communication without installing into Home Assistant.

### Option 1: Using `uv` (Fastest)

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run the test script with uv (no venv needed!)
uv run test_connection.py 192.168.1.100

# Or specify a custom port
uv run test_connection.py 192.168.1.100 30000
```

### Option 2: Using `venv`

```bash
# Create a virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# or
.\venv\Scripts\activate   # On Windows

# Run the test
python test_connection.py 192.168.1.100

# When done, deactivate
deactivate
```

### What the Test Does

The test script will:

1. ✅ Connect to your device via UDP
2. ✅ Retrieve device information (model, firmware, MAC addresses)
3. ✅ Get battery status (SOC, capacity, temperature)
4. ✅ Get energy system data (power flows, energy totals)
5. ✅ Get current operating mode
6. ✅ Try to get energy meter data (if CT sensors connected)

### Expected Output

```
============================================================
Testing Marstek Venus E at 192.168.1.100:30000
============================================================

📡 Connecting to device...
✅ Connected successfully

📋 Getting device information...
✅ Device Info:
   Model: VenusE
   Firmware Version: 111
   WiFi MAC: 123456789012
   BLE MAC: 123456789012
   WiFi Network: MY_HOME
   IP Address: 192.168.1.100

🔋 Getting battery status...
✅ Battery Status:
   SOC: 98%
   Capacity: 2508.0 Wh
   Rated Capacity: 2560.0 Wh
   Temperature: 25.0°C
   Charging Enabled: True
   Discharging Enabled: True

⚡ Getting energy system status...
✅ Energy System Status:
   Battery SOC: 98%
   Battery Capacity: 2560.0 Wh
   Battery Power: 0.0 W
   PV Power: 580.0 W
   Grid Power: 100.0 W
   Load Power: 0.0 W

   Total PV Energy: 12345.0 Wh
   Total Grid Input: 1607.0 Wh
   Total Grid Output: 844.0 Wh
   Total Load Energy: 5678.0 Wh

🎛️  Getting operating mode...
✅ Operating Mode:
   Mode: Auto
   Grid Power: 100.0 W
   Load Power: 0.0 W
   Battery SOC: 98%

============================================================
✅ ALL TESTS PASSED!
============================================================

Your device is working correctly and ready for Home Assistant.
```

## Full Integration Test: Install in Home Assistant

Once the standalone test passes, install the integration in Home Assistant.

### Step 1: Copy Integration Files

```bash
# Find your Home Assistant config directory
# Usually: ~/.homeassistant or /config (in Docker/HAOS)

# Copy the integration
cp -r custom_components/marstek_venus /path/to/homeassistant/custom_components/

# Example for typical locations:
# cp -r custom_components/marstek_venus ~/.homeassistant/custom_components/
# cp -r custom_components/marstek_venus /config/custom_components/
```

### Step 2: Restart Home Assistant

Restart HA to load the new integration:

- Settings > System > Restart
- Or via CLI: `ha core restart`

### Step 3: Add the Integration

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Marstek Venus E"
4. Enter your device IP address and port
5. Click **Submit**

### Step 4: Verify Entities

After adding, you should see:

**Sensors (11 total):**

- Battery (%)
- Battery Capacity (Wh)
- Battery Power (W)
- Battery Temperature (°C)
- Solar Power (W)
- Grid Power (W)
- Load Power (W)
- Total Solar Energy (Wh)
- Total Grid Import Energy (Wh)
- Total Grid Export Energy (Wh)
- Total Load Energy (Wh)

**Controls (1 total):**

- Operating Mode (select: Auto/AI/Passive)

### Step 5: Check Logs

Monitor logs for errors:

- Settings > System > Logs
- Or view the log file: `home-assistant.log`

Look for lines containing `marstek_venus`:

```bash
# View logs in real-time
tail -f /path/to/homeassistant/home-assistant.log | grep marstek
```

## Troubleshooting

### Test Script Fails with "Connection Error"

**Symptoms:**

```
❌ Connection Error: Failed to connect: ...
```

**Solutions:**

1. Verify device IP address:

   ```bash
   ping 192.168.1.100
   ```

2. Check Open API is enabled in Marstek mobile app
3. Ensure device is on same network as your computer
4. Try different UDP port if you changed it in the app
5. Check firewall isn't blocking UDP traffic

### Test Script Fails with "Timeout Error"

**Symptoms:**

```
❌ Timeout Error: Device did not respond
```

**Solutions:**

1. Device may be busy - wait and try again
2. Increase timeout in `const.py` (change `TIMEOUT = 10` to `TIMEOUT = 20`)
3. Check network latency: `ping -c 10 192.168.1.100`

### Integration Not Appearing in HA

**Solutions:**

1. Verify files are in correct location:

   ```bash
   ls -la /path/to/homeassistant/custom_components/marstek_venus/
   ```

2. Check file permissions (should be readable)
3. Check HA logs for Python errors
4. Try clearing browser cache and refreshing
5. Restart HA again

### Entities Show "Unavailable"

**Solutions:**

1. Check HA logs for connection errors
2. Run standalone test script to verify device is reachable
3. Check if device Open API is still enabled
4. Try reloading the integration:
   - Settings > Devices & Services
   - Find Marstek Venus E
   - Click three dots > Reload

### Mode Selection Doesn't Work

**Symptoms:**

- Can select mode but doesn't change
- Mode reverts to previous value

**Solutions:**

1. Check HA logs for API errors
2. Verify you have permission to control the device
3. Try using the Marstek mobile app to verify device is controllable
4. Some modes may be disabled by device firmware

## Advanced Testing

### Test Mode Changes

```python
# Create a test script to change modes
import asyncio
from custom_components.marstek_venus.api import MarstekApiClient

async def test_mode_change():
    client = MarstekApiClient("192.168.1.100", 30000)
    await client.connect()

    # Change to AI mode
    result = await client.set_mode("AI", {"ai_cfg": {"enable": 1}})
    print(f"Mode change result: {result}")

    # Verify
    mode = await client.get_mode()
    print(f"Current mode: {mode}")

    await client.close()

asyncio.run(test_mode_change())
```

### Monitor Real-time Data

```bash
# Watch sensor values update
watch -n 5 'python test_connection.py 192.168.1.100'
```

## Development Testing

### Run with Home Assistant Core (for development)

If you're developing and want to test with HA core:

```bash
# Clone HA core
git clone https://github.com/home-assistant/core.git
cd core

# Setup development environment
script/setup

# Activate venv
source venv/bin/activate

# Copy integration
cp -r /path/to/ha-marstek-venus/custom_components/marstek_venus config/custom_components/

# Run HA
hass -c config
```

### Unit Tests (Future)

Unit tests will be added in a future version using pytest:

```bash
# Install test dependencies
uv pip install pytest pytest-asyncio pytest-homeassistant-custom-component

# Run tests
pytest tests/
```

## Getting Help

If you encounter issues:

1. Check the [README.md](README.md) for common solutions
2. Review the [API documentation](docs/MarstekDeviceOpenApi.pdf)
3. Check Home Assistant logs for detailed error messages
4. Open an issue on GitHub with:
   - Output from `test_connection.py`
   - Relevant HA log entries
   - Device model and firmware version
