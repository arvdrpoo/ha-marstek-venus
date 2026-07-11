# Device Setup Guide

## Current Status

✅ **Network Connection**: Device is reachable at `192.168.1.195`
❌ **API Status**: Open API is not responding (likely not enabled)

## What You Need to Do

The Marstek Venus E device's Open API feature must be enabled before the Home Assistant integration can work.

### Step 1: Enable Open API in Marstek Mobile App

1. **Open the Marstek mobile app** on your phone
2. **Connect to your Venus E device** (should show as connected)
3. **Go to device settings** (usually a gear/settings icon)
4. **Find the "Open API" or "Local API" setting**
   - This might be under: Settings → Advanced → Open API
   - Or: Device → API Settings → Enable Local API
5. **Enable the Open API feature**
6. **Note the UDP port number** displayed (default is 30000)
   - Recommended: Use a port between 49152-65535
   - Example: 50000, 51234, etc.

### Step 2: Verify API is Enabled

After enabling, run the diagnostic script to test:

```bash
# Test with default port
python3 diagnose.py 192.168.1.195

# Or if you changed the port in the app:
python3 diagnose.py 192.168.1.195 YOUR_PORT
```

### Expected Success Output

When the API is properly enabled, you should see:

```
✅ SUCCESS! Device responded!

Device Information:
   device: VenusE
   ver: 111
   ble_mac: 123456789012
   wifi_mac: 123456789012
   wifi_name: YOUR_WIFI_NAME
   ip: 192.168.1.195
```

## Current Test Results

We sent the following request to your device:

```json
{
  "id": 1,
  "method": "Marstek.GetDevice",
  "params": {"ble_mac": "0"}
}
```

**Result**: `Connection refused` - No service listening on port 30000

This confirms the Open API is not currently enabled on the device.

## Troubleshooting

### "I enabled the API but still getting connection refused"

1. **Check the port number** in the app - it might not be 30000
2. **Restart the device** after enabling the API
3. **Check device firmware version** - very old firmware might not support the API
4. **Try a different port** - some firmware versions have port restrictions

### "I can't find the Open API setting in the app"

1. **Update the Marstek app** to the latest version
2. **Update device firmware** via the app
3. **Check device model** - confirm it's Venus E 3 and supports the local API
4. **Contact Marstek support** - they can confirm if your model/firmware supports it

### "The setting is there but greyed out"

1. **Check internet connection** - some devices require cloud connection first
2. **Complete device setup** - ensure basic configuration is done
3. **Update firmware** - might be required before enabling API

## Once API is Working

After you see the success message from `diagnose.py`:

1. Run the full test: `python3 test_device.py 192.168.1.195`
2. Install the integration in Home Assistant
3. Configure with your device's IP and port

## Additional Help

- **Marstek Support**: Contact them for help enabling the API
- **API Documentation**: See `docs/MarstekDeviceOpenApi.pdf` section 2.2.1
- **GitHub Issues**: Report issues at the GitHub repository

## Network Information

Your setup:
- **Device IP**: 192.168.1.195
- **Test machine IP**: 192.168.1.6
- **Network latency**: 94-176ms (normal for WiFi)
- **Port being tested**: 30000 (UDP)
