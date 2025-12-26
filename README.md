# Marstek Venus E 3 - Home Assistant Integration

A custom Home Assistant integration for the Marstek Venus E 3 home battery system, using its local UDP API.

## Features

- **Battery Monitoring**: Track battery state of charge, capacity, power, and temperature
- **Power Flow Monitoring**: Monitor solar (PV), grid, and load power in real-time
- **Energy Statistics**: Track cumulative energy from solar, grid import/export, and load consumption
- **Operating Mode Control**: Switch between Auto, AI, and Passive modes
- **Local Control**: Communicates directly with your device over your local network (no cloud required)
- **Real-time Updates**: Data refreshes every 30 seconds

## Supported Devices

- Marstek Venus E 3
- Marstek Venus C (should work, untested)
- Other Marstek devices with local UDP API support may work

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/arvdrpoo/ha-marstek-venus-e`
6. Select "Integration" as the category
7. Click "Add"
8. Find "Marstek Venus E" in the integration list and install it
9. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/marstek_venus_e` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

### Prerequisites

Before adding the integration, ensure that:

1. Your Marstek Venus E device is connected to your home network
2. The Open API feature has been enabled in the Marstek mobile app
3. You know the IP address of your device (check your router or the Marstek app)
4. Optional: Configure a static IP address for your device in your router settings

### Adding the Integration

1. In Home Assistant, go to **Settings** > **Devices & Services**
2. Click the **+ Add Integration** button
3. Search for "Marstek Venus E"
4. Enter your device's IP address
5. Optionally change the UDP port (default: 30000) and device name
6. Click **Submit**

The integration will validate the connection and create the device with all entities.

## Entities

### Sensors

**Battery Sensors:**
- `Battery` - Battery state of charge (%)
- `Battery Capacity` - Current battery capacity (Wh)
- `Battery Power` - Battery charging/discharging power (W, positive = charging)
- `Battery Temperature` - Battery temperature (°C)

**Power Flow Sensors:**
- `Solar Power` - Solar panel power generation (W)
- `Grid Power` - Grid import/export power (W, positive = exporting to grid)
- `Load Power` - Load consumption power (W)

**Energy Total Sensors:**
- `Total Solar Energy` - Cumulative solar energy generated (Wh)
- `Total Grid Import Energy` - Cumulative energy imported from grid (Wh)
- `Total Grid Export Energy` - Cumulative energy exported to grid (Wh)
- `Total Load Energy` - Cumulative load consumption (Wh)

### Controls

**Select Entity:**
- `Operating Mode` - Switch between Auto, AI, and Passive modes
  - **Auto**: Automatic mode - device manages itself
  - **AI**: AI-based optimization mode
  - **Passive**: Manual power control mode (set to 0W standby by default)

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

### Passive Mode Not Working as Expected

- Passive mode defaults to 0W with a 300-second countdown
- For custom power settings, advanced configuration will be added in a future release
- Consider using Auto or AI mode for typical operation

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
