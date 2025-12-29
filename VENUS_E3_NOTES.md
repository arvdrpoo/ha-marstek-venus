# Marstek Venus E 3 - Integration Notes

## ✅ Status: FULLY WORKING

All API communication is working correctly with your Venus E 3 device at `192.168.1.194`.

## Device Information

- **Model**: VenusE 3.0
- **Firmware**: v144
- **WiFi MAC**: 98254a07299e
- **Network**: Zonneburg #10
- **Battery**: 5120 Wh capacity (currently 12% charged)
- **CT Sensors**: Connected and working (measuring 342W across 3 phases)

## API Support on Venus E 3

The Venus E 3 supports a **subset** of the API documented in `docs/MarstekDeviceOpenApi.pdf`. The documentation appears to cover multiple models (Venus C, D, E), but not all endpoints work on the E 3.

### ✅ Supported Endpoints

| Endpoint | Purpose | Works | Notes |
|----------|---------|-------|-------|
| `Marstek.GetDevice` | Device info | ✅ Yes | MAC, IP, WiFi name |
| `ES.GetStatus` | Energy system | ✅ Yes | Includes battery data! |
| `EM.GetStatus` | Energy meter | ✅ Yes | CT sensor readings |

### ❌ Unsupported Endpoints

| Endpoint | Purpose | Works | Alternative |
|----------|---------|-------|-------------|
| `Bat.GetStatus` | Battery details | ❌ No | Use `ES.GetStatus` instead |
| `ES.GetMode` | Get operating mode | ❌ No | Not available |
| `ES.SetMode` | Set operating mode | ❌ No | Not available |
| `Wifi.GetStatus` | WiFi details | ❌ No | Use `Marstek.GetDevice` |

## Important Device Quirks

### 1. Rate Limiting

**The device requires a 2+ second delay between API requests.**

- First request: Works immediately
- Second request: Times out if sent < 2 seconds after first
- With 2s delay: All requests work perfectly

**Impact on Integration:**
- ✅ Home Assistant polls every 30 seconds (plenty of time)
- ✅ No issues expected in normal operation
- ⚠️  Manual testing requires delays between commands

### 2. ES.GetStatus Includes Battery Data

The `ES.GetStatus` endpoint returns battery data that would normally come from `Bat.GetStatus`:

```json
{
  "bat_soc": 12,      // Battery state of charge (%)
  "bat_cap": 5120,    // Battery capacity (Wh)
  "pv_power": 0,      // Solar power
  "ongrid_power": 0,  // Grid power
  ...
}
```

This is actually better - one API call gives us everything!

### 3. No Mode Control

The Venus E 3 does not support:
- Getting current operating mode
- Setting operating mode (Auto/AI/Manual/Passive)

This means the `select` platform for mode control will not work and should be removed or disabled for Venus E 3 users.

## Integration Updates Made

### 1. Coordinator (`coordinator.py`)

Updated to:
- Only call `ES.GetStatus` and `EM.GetStatus`
- Construct `bat_data` from ES response
- Set `mode_data` to "Unknown" (not supported)
- Handle 30-second polling (no rate limit issues)

### 2. Sensor Platform (`sensor.py`)

Battery sensors now get data from `ES.GetStatus`:
- `battery_soc`: From `es.bat_soc`
- `battery_capacity`: From `es.bat_cap`
- `battery_power`: Not available on Venus E 3
- `battery_temperature`: Not available on Venus E 3

### 3. Select Platform (`select.py`)

Mode control not supported on Venus E 3. Options:
- Remove select platform entirely
- Hide it for Venus E 3 devices (detect by model)
- Show as read-only "Unknown"

## Available Sensors

Based on successful API testing:

### Battery (from ES.GetStatus)
- ✅ Battery SOC (%)
- ✅ Battery Capacity (Wh)
- ❌ Battery Power (W) - not provided
- ❌ Battery Temperature (°C) - not provided

### Power Flows (from ES.GetStatus)
- ✅ Solar Power (W)
- ✅ Grid Power (W)
- ✅ Load Power (W)

### Energy Totals (from ES.GetStatus)
- ✅ Total Solar Energy (Wh)
- ✅ Total Grid Import (Wh)
- ✅ Total Grid Export (Wh)
- ✅ Total Load Energy (Wh)

### CT Sensors (from EM.GetStatus)
- ✅ Phase A Power (W)
- ✅ Phase B Power (W)
- ✅ Phase C Power (W)
- ✅ Total Power (W)
- ✅ CT Connection State

## Testing Results

### Raw API Test
```bash
python3 test_raw.py
```
✅ All supported endpoints tested individually

### Comprehensive Test
```bash
python3 test_venus3.py
```
✅ Full device test with proper delays
✅ Shows all available data
✅ Confirms CT sensors working

### Current Device State
- Battery: 12% (5120 Wh)
- Grid: 0W
- Solar: 0W (nighttime)
- CT Total: 342W across 3 phases

## Home Assistant Installation

The integration is ready to install:

```bash
# 1. Copy integration files
cp -r custom_components/marstek_venus ~/.homeassistant/custom_components/

# 2. Restart Home Assistant

# 3. Add integration:
#    Settings > Devices & Services > Add Integration
#    Search: "Marstek Venus E"
#    IP: 192.168.1.194
#    Port: 30000
```

### Expected Entities

**Sensors (9 total):**
- Battery (%)
- Battery Capacity (Wh)
- Solar Power (W)
- Grid Power (W)
- Load Power (W)
- Total Solar Energy (Wh)
- Total Grid Import Energy (Wh)
- Total Grid Export Energy (Wh)
- Total Load Energy (Wh)
- + CT sensor entities if connected

**Controls:**
- None (mode control not supported on Venus E 3)

## Recommendations

1. **Remove Select Platform**: Mode control doesn't work on Venus E 3
2. **Update README**: Document Venus E 3 limitations
3. **Device Detection**: Auto-detect Venus E 3 and adjust features
4. **Polling Interval**: 30 seconds is perfect (2s minimum required)

## Files for Testing

- `test_device.py` - Comprehensive device test (use this!)
- `diagnose.py` - Network connectivity diagnostics
- `marstek_api.py` - Standalone API client

## Next Steps

1. ✅ API working perfectly
2. ✅ All available data identified
3. ✅ Integration updated for Venus E 3
4. ⏳ **Test in Home Assistant** (next!)
5. ⏳ Update documentation for Venus E 3 limitations
6. ⏳ Consider removing/disabling mode control

---

**Tested with**: Venus E 3.0, Firmware v144, IP 192.168.1.194
**Date**: 2025-12-26
