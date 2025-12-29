# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration for the Marstek Venus home battery system. The integration communicates with the device using its local UDP API to monitor battery status, energy flow, and control operating modes.

## Marstek API Architecture

### Protocol Format
- **Transport**: UDP over LAN (default port 30000, configurable 49152-65535)
- **Format**: JSON-RPC style with `id`, `method`, `params` structure
- **Communication**: Request/response pattern, device responds with `src` and either `result` or `error`

### Device Discovery
Devices are discovered via UDP broadcast to `255.255.255.255`:
```json
{"id": 0, "method": "Marstek.GetDevice", "params": {"ble_mac":"0"}}
```
Response includes device model, firmware version, MAC addresses, IP, and WiFi info.

### API Components

The Marstek API is organized into components, each with GetStatus and sometimes SetMode methods:

1. **Marstek** - Device discovery and basic info
   - `Marstek.GetDevice`: Discover devices on LAN

2. **WiFi** - Network configuration
   - `Wifi.GetStatus`: Get WiFi connection details, signal strength, IP config

3. **BLE** (Bluetooth) - Bluetooth status
   - `BLE.GetStatus`: Get Bluetooth state and MAC

4. **Bat** (Battery) - Battery information
   - `Bat.GetStatus`: SOC, charging/discharge flags, temperature, capacity (Wh)

5. **PV** (Photovoltaic) - Solar panel data
   - `PV.GetStatus`: Power, voltage, current from solar

6. **ES** (Energy System) - Main control and monitoring
   - `ES.GetStatus`: Overall system status, power flows, energy totals
   - `ES.SetMode`: Configure operating mode (Auto/AI/Manual/Passive)
   - `ES.GetMode`: Get current operating mode and power output

7. **EM** (Energy Meter) - CT sensor data
   - `EM.GetStatus`: Current transformer status, per-phase power

### Operating Modes

The device supports 4 operating modes via `ES.SetMode`:

- **Auto**: Automatic mode (enable: 1)
- **AI**: AI-based mode (enable: 1)
- **Manual**: Time-based scheduling with power settings
  - Supports 10 time periods (time_num: 0-9)
  - Each period: start_time, end_time, week_set (bitmap), power (W), enable
- **Passive**: Direct power control with countdown
  - Set power (W) and cd_time (countdown in seconds)

### Key Data Points

From `ES.GetStatus`:
- `bat_soc`: Battery state of charge (%)
- `bat_cap`: Total battery capacity (Wh)
- `pv_power`: Solar charging power (W)
- `ongrid_power`: Grid-tied power (W, positive = export)
- `offgrid_power`: Off-grid/load power (W)
- `bat_power`: Battery power (W, positive = charging)
- `total_pv_energy`: Cumulative solar energy (Wh)
- `total_grid_output_energy`: Cumulative grid export (Wh)
- `total_grid_input_energy`: Cumulative grid import (Wh)
- `total_load_energy`: Cumulative load consumption (Wh)

### Error Handling

Standard JSON-RPC error codes:
- `-32700`: Parse error
- `-32600`: Invalid request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error
- `-32000 to -32099`: Server errors

## Device Models

Different Marstek models support different components:

- **Venus C/E**: Marstek, WiFi, Bluetooth, Battery, ES, EM (no PV component)
- **Venus D**: Marstek, WiFi, Bluetooth, Battery, PV, ES, EM (includes PV)

This integration targets Venus E 3, which has the same component set as Venus C.

## Home Assistant Integration Structure

Standard HA custom integration structure expected:
```
custom_components/marstek_venus/
├── __init__.py          # Integration setup, config entry handling
├── manifest.json        # Integration metadata
├── config_flow.py       # UI-based configuration
├── const.py            # Constants (domain, default port, etc.)
├── coordinator.py      # DataUpdateCoordinator for polling device
├── sensor.py           # Sensor entities (SOC, power, energy, etc.)
├── switch.py           # Switch entities if needed
├── select.py           # Mode selection entity
└── translations/
    └── en.json         # UI strings
```

## Development Guidelines

### UDP Communication
- Use asyncio UDP sockets for non-blocking I/O
- Implement proper timeout handling (recommended 5-10s for responses)
- Support both unicast (to known IP) and broadcast (for discovery)
- Handle JSON parsing errors gracefully
- Device IP should be configurable with option to use static IP

### Data Polling
- Use Home Assistant's `DataUpdateCoordinator` for efficient polling
- Recommended poll interval: 30-60 seconds for normal data
- Consider separate faster polling for real-time power data if needed
- Batch multiple component queries if possible

### Entity Organization
Suggested sensor entities:
- Battery: SOC, capacity, temperature, charge/discharge flags
- Power flows: PV power, grid power, battery power, load power
- Energy totals: PV energy, grid import/export, load energy
- Network: WiFi signal strength, connection status
- CT clamps: Per-phase power readings (if connected)

Suggested select entity:
- Operating mode selector (Auto/AI/Manual/Passive)

### Configuration
- Device IP address (required)
- UDP port (default 30000)
- Poll interval (default 30s)
- Device name/model for identification

## API Reference Location

Complete API documentation is in `docs/MarstekDeviceOpenApi.pdf` including:
- Detailed parameter descriptions for all methods
- Example requests and responses
- Data types and units for all fields
- Week bitmask encoding for Manual mode schedules
