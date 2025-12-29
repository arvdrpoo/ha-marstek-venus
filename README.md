# Marstek Venus E 3 - Home Assistant Integration

A custom Home Assistant integration for the Marstek Venus E 3 home battery system, using its local UDP API.

## Features

- **Battery Monitoring**: Track battery state of charge and capacity
- **Power Flow Monitoring**: Monitor solar (PV), grid, and load power in real-time
- **Energy Statistics**: Track cumulative energy from solar, grid import/export, and load consumption
- **Local Control**: Communicates directly with your device over your local network (no cloud required)
- **Real-time Updates**: Data refreshes every 30 seconds

**Note**: This integration supports all Venus E component functionalities (Battery, ES, EM). Some sensors may show 0 values if optional features aren't connected (e.g., solar panels, load monitoring). Mode control may not be available on all Venus E 3 hardware revisions.

## Supported Devices

- Marstek Venus E 3 (tested and confirmed working)

## Installation

### Prerequisites

Before installation:
- Home Assistant 2024.1.0 or later
- HACS installed ([installation guide](https://hacs.xyz/docs/setup/download))
- Marstek Venus E device connected to your network
- Open API enabled in the Marstek mobile app (Settings > Enable Open API)
- Device IP address (find in router or Marstek app)

### HACS Installation (Recommended)

1. **Add Custom Repository**
   - Open HACS > Integrations
   - Click menu (⋮) > Custom repositories
   - Add repository: `https://github.com/arvdrpoo/ha-marstek-venus-e`
   - Category: `Integration`
   - Click Add

2. **Install Integration**
   - Click "Explore & Download Repositories"
   - Search for "Marstek Venus E"
   - Click Download
   - Restart Home Assistant

3. **Add Integration**
   - Go to Settings > Devices & Services
   - Click "+ Add Integration"
   - Search for "Marstek Venus E"
   - Enter your device IP address (e.g., `192.168.1.100`)
   - Optionally configure port (default: 30000) and device name
   - Click Submit

### Manual Installation

1. Download the [latest release](https://github.com/arvdrpoo/ha-marstek-venus-e/releases)
2. Copy `custom_components/marstek_venus_e` to your `config/custom_components/` directory
3. Restart Home Assistant
4. Follow step 3 above to add the integration

### Common Setup Issues

- **Cannot connect**: Verify IP address, ensure device is powered on and Open API is enabled
- **Port error**: Use default port 30000 unless specifically changed
- **Entities unavailable**: Wait 30-60 seconds for first update, check logs if persists

## Entities

### Sensors (9 total)

**Battery Sensors:**
- `Battery` - Battery state of charge (%)
- `Battery Capacity` - Current battery capacity (Wh)

**Power Flow Sensors:**
- `Solar Power` - Solar panel power generation (W) *
- `Grid Power` - Grid import/export power (W, positive = exporting to grid)
- `Load Power` - Load consumption power (W) *

**Energy Total Sensors:**
- `Total Solar Energy` - Cumulative solar energy generated (Wh) *
- `Total Grid Import Energy` - Cumulative energy imported from grid (Wh)
- `Total Grid Export Energy` - Cumulative energy exported to grid (Wh)
- `Total Load Energy` - Cumulative load consumption (Wh) *

\* May show 0 if optional components are not connected

### Controls

**Select Entity:**
- `Operating Mode` - Switch between operating modes **
  - **Auto**: Automatic mode - device manages itself
  - **AI**: AI-based optimization mode
  - **Manual**: Manual power control mode with scheduling
  - **Passive**: Direct power control mode (defaults to 0W standby)

\*\* Mode control may not be supported on all Venus E 3 hardware revisions. If unavailable, the mode will show as "Unknown".

## API Information

This integration communicates with the Marstek device using its local UDP API on port 30000 (configurable). The API uses a JSON-RPC style protocol.

Complete API documentation is available in `docs/MarstekDeviceOpenApi.pdf`.

## Troubleshooting

### Device Not Found

- Verify the IP address is correct
- Ensure the device is powered on and connected to your network
- Check that the Open API feature is enabled in the Marstek app
- Verify the UDP port (default 30000) is not blocked by your firewall
- Try restarting the Marstek device

### Entities Unavailable

- Check Home Assistant logs for errors
- Verify network connectivity between Home Assistant and the device
- Ensure the device's UDP API hasn't been disabled in the mobile app
- Try reloading the integration from Settings > Devices & Services


## Development

See [CLAUDE.md](CLAUDE.md) for detailed information about the codebase architecture and development guidelines.

### Testing with Docker

Test the integration locally using the included Docker Compose setup:

```bash
# Start Home Assistant test instance
docker-compose up -d

# View logs
docker-compose logs -f homeassistant

# Restart after code changes
docker-compose restart homeassistant

# Stop test instance
docker-compose down
```

Access Home Assistant at http://localhost:8123. The integration is mounted read-only from `custom_components/marstek_venus_e`. First startup takes 1-2 minutes to initialize.

### Testing the API Client

Test the standalone API client without Home Assistant:

```bash
# Test connection to your device (no dependencies required)
python3 test_device.py 192.168.1.194

# Run diagnostic tests
python3 diagnose.py 192.168.1.194
```

### Code Structure

```
custom_components/marstek_venus_e/
├── __init__.py          # Integration setup
├── manifest.json        # Integration metadata
├── const.py            # Constants
├── api.py              # UDP API client
├── config_flow.py      # UI configuration flow
├── coordinator.py      # Data update coordinator
├── sensor.py           # Sensor entities
├── select.py           # Mode selection entity
├── strings.json        # UI strings
└── translations/
    └── en.json         # English translations
```

## Future Enhancements

- [ ] Manual mode scheduling support (time-based power control)
- [ ] Configuration options for poll interval and timeout
- [ ] WiFi network information sensors
- [ ] Service calls for advanced control
- [ ] Energy dashboard integration improvements
- [ ] Diagnostic entities for debugging

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This integration is provided "as is" for local use only. The author is not affiliated with Marstek and is not liable for any damages, data loss, or issues caused by using this integration. Use at your own risk.

## Acknowledgments

- Thanks to Marstek for providing the local API documentation
- Built using the Home Assistant integration best practices
