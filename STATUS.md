# Project Status - Marstek Venus E Home Assistant Integration

## ✅ What's Been Built

### Complete Home Assistant Integration
All integration files are ready in `custom_components/marstek_venus/`:
- Python modules implementing sensors, controls, and API communication
- **~24 entities**: battery, power flows, energy totals, CT phases, mode,
  and diagnostics (Connection, Last Seen); optional WiFi/BLE/PV sensors
- **1 select entity**: Operating mode control (Auto/AI/Manual/Passive)
- Config flow with UDP-broadcast device discovery, DHCP discovery, and manual entry
- Resilient to connection loss: rides out short outages, marks entities
  unavailable during long ones, and recovers automatically

### Standalone Testing Tools
No Home Assistant or virtual environment needed:
- **`custom_components/marstek_venus/api.py`**: Standalone API client (418 lines, pure Python)
- **`test_device.py`**: Full device test (shows all sensors/data)
- **`diagnose.py`**: Low-level UDP diagnostic tool

### Complete Documentation
- **README.md**: User guide with features, installation, troubleshooting
- **QUICKSTART.md**: 2-minute setup guide
- **TESTING.md**: Comprehensive testing guide
- **DEVICE_SETUP.md**: How to enable API on your device
- **CLAUDE.md**: Architecture and development guide

## 🔧 Test Results

Validated end-to-end against a **Marstek VenusE 3.0** (firmware 148):

✅ **Network**: Reachable
✅ **API**: Responds to `Marstek.GetDevice`, `ES.GetStatus`, `Bat.GetStatus`,
   `EM.GetStatus`, `ES.GetMode`
✅ **Discovery**: Device found via UDP broadcast
✅ **Home Assistant**: Config entry loads with ~24 live entities

> Note: the Marstek app can toggle the Local API back off on its own. If the
> device stops responding, re-check the Local API setting in the app. The
> integration tolerates this and recovers when the API returns.

## 📋 Prerequisite: Enable the Local API

If the device does not respond, enable its Local (Open) API:

1. Open the **Marstek mobile app**
2. Go to your **Venus E device settings**
3. Find and **enable "Open API"** or "Local API"
4. Note the **UDP port number** (usually 30000)

See **`DEVICE_SETUP.md`** for detailed instructions.

### Verify and install

```bash
# Verify the API is up
python3 diagnose.py 192.168.1.194

# Full device test (battery, power, energy, CT)
python3 test_device.py 192.168.1.194
```

For HACS: add this repository as a custom integration, install, restart Home
Assistant, then add it from Settings > Devices & Services (it may already be
discovered). For a manual install, copy `custom_components/marstek_venus` into
your HA `custom_components/` directory and restart.

## 📁 Key Files

| File | Purpose |
|------|---------|
| `custom_components/marstek_venus/api.py` | Standalone API client (no HA deps) |
| `test_device.py` | Quick device test |
| `diagnose.py` | Detailed UDP diagnostics |
| `DEVICE_SETUP.md` | How to enable API on device |
| `QUICKSTART.md` | Fast setup guide |
| `custom_components/marstek_venus/` | Full HA integration |

## 🎯 Testing Summary

### What Works
- ✅ UDP broadcast discovery
- ✅ Live data via ES/Bat/EM/GetMode
- ✅ Home Assistant config entry + entities
- ✅ Resilient reconnect and Last Seen tracking
- ✅ Operating mode control

### Requires user action
- ⚠️ Local API must be enabled in the Marstek app (and can be toggled off by it)

## 🚀 Once API is Enabled

You'll be able to:
1. See real-time battery status
2. Monitor solar, grid, and load power
3. Track energy production/consumption
4. Control operating modes from HA
5. Create automations based on battery state
6. Add to Energy Dashboard

## 📞 Getting Help

1. **API not enabling**: Contact Marstek support
2. **Different port**: Run `python3 diagnose.py 192.168.1.195 PORT`
3. **Integration issues**: Check Home Assistant logs
4. **Questions**: See documentation or open GitHub issue

## 🔍 Diagnostic Commands

```bash
# Check if device is reachable
ping 192.168.1.195

# Test UDP communication (detailed)
python3 diagnose.py 192.168.1.195

# Full device test (after API enabled)
python3 test_device.py 192.168.1.195

# Test with different port
python3 diagnose.py 192.168.1.195 50000
```

---

**Status**: Deployed and working; validated end-to-end in Home Assistant.

**Last tested**: Marstek VenusE 3.0 (fw 148) - config entry loaded with live data.

See `DEVICE_SETUP.md` if the device's Local API needs enabling.
