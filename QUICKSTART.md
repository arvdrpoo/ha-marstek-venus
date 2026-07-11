# Quick Start Guide

Get up and running in 2 minutes!

## Prerequisites

- Your Marstek Venus E device IP address (e.g., `192.168.1.100`)
- Open API enabled in the Marstek mobile app
- `uv` installed (or Python 3.11+)

## Step 1: Test Your Device Connection

### Using `uv` (recommended)

```bash
# If you don't have uv, install it first:
# curl -LsSf https://astral.sh/uv/install.sh | sh

# Test the connection (replace IP with your device's IP)
uv run test_device.py 192.168.1.100
```

### Using Python directly

```bash
# Create venv
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux

# Run test
python test_device.py 192.168.1.100

# Deactivate when done
deactivate
```

### Expected Result

You should see output like:

```
============================================================
Testing Marstek Venus E at 192.168.1.100:30000
============================================================

📡 Connecting to device...
✅ Connected successfully

📋 Getting device information...
✅ Device Info:
   Model: VenusE
   ...

✅ ALL TESTS PASSED!
```

**If the test fails**, see [TESTING.md](TESTING.md) for troubleshooting.

## Step 2: Install in Home Assistant

### Copy Integration Files

```bash
# Find your HA config directory and copy files
# Replace /path/to/homeassistant with your actual path

cp -r custom_components/marstek_venus ~/.homeassistant/custom_components/

# Common paths:
# ~/.homeassistant/custom_components/          (Linux/macOS)
# /config/custom_components/                    (Home Assistant OS/Docker)
# C:\Users\YourName\.homeassistant\custom_components\  (Windows)
```

### Restart Home Assistant

```bash
# Via UI: Settings > System > Restart
# Or via CLI: ha core restart
```

## Step 3: Add the Integration

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration** (bottom right)
3. Search for **"Marstek Venus E"**
4. Pick your device from the discovered list, or choose "Enter IP address
   manually" and type it in (e.g., `192.168.1.100`)
5. Click **Submit**

> Devices on your network are found automatically by UDP broadcast, and Home
> Assistant may also surface the device on its own via DHCP. Autodiscovery
> needs Home Assistant to be on the same network segment; in Docker that means
> `network_mode: host`. Manual IP entry always works.

## Step 4: Done! 🎉

You should now see:
- 1 device: "Marstek VenusE" (or similar), plus a separate "CT Meter" device
- ~24 entities: battery, power flows, energy totals, CT phases, mode,
  and diagnostics (Connection, Last Seen, ...)
- 1 control: Operating mode selector

### View Your Data

- Dashboard > Add Card > Choose any sensor
- Or go to Settings > Devices & Services > Marstek Venus E

### Control Operating Mode

Use the "Operating Mode" selector to switch between:
- **Auto** - Automatic operation
- **AI** - AI-based optimization
- **Manual** - Time-based power schedules (configure via services)
- **Passive** - Direct power control with a countdown

## Troubleshooting

### "Integration not found"

- Verify files copied correctly: `ls ~/.homeassistant/custom_components/marstek_venus/`
- Restart Home Assistant again
- Clear browser cache

### "Cannot connect to device"

- Run the test script again: `uv run test_device.py YOUR_IP`
- Check device is powered on and on network
- Verify Open API is still enabled in Marstek app

### Entities show "Unavailable"

- Check Settings > System > Logs for errors
- Try reloading: Settings > Devices & Services > Marstek > ⋮ > Reload

## Next Steps

- Add sensors to your Energy Dashboard
- Create automations based on battery SOC
- Monitor power flows in real-time
- See [README.md](README.md) for full documentation

## Need More Help?

- Detailed testing guide: [TESTING.md](TESTING.md)
- Architecture info: [CLAUDE.md](CLAUDE.md)
- API reference: [docs/MarstekDeviceOpenApi.pdf](docs/MarstekDeviceOpenApi.pdf)
- Report issues: https://github.com/arvdrpoo/ha-marstek-venus/issues
