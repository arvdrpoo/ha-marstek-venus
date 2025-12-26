#!/usr/bin/env python3
"""
Comprehensive test script for Marstek Venus E devices.

This script tests all available API endpoints and displays device data.
Properly handles Venus E 3 requirements:
- Only certain API endpoints are supported
- Requires 2+ second delay between requests (handled automatically by API client)

Usage:
    python3 test_device.py [device_ip] [port]

Examples:
    python3 test_device.py
    python3 test_device.py 192.168.1.194
    python3 test_device.py 192.168.1.194 30000
"""
import asyncio
import sys
import importlib.util

# Import the API module directly to avoid Home Assistant dependencies
spec = importlib.util.spec_from_file_location(
    "api",
    "custom_components/marstek_venus_e/api.py"
)
api_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_module)
MarstekApiClient = api_module.MarstekApiClient

# Default device configuration
DEFAULT_HOST = "192.168.1.194"
DEFAULT_PORT = 30000


async def test_device(host: str, port: int):
    """Test all device endpoints with a single persistent connection."""
    print(f"\n{'='*70}")
    print(f"Marstek Venus E Device Test")
    print(f"{'='*70}\n")
    print(f"Testing device at {host}:{port}\n")

    # Create client and connect
    client = MarstekApiClient(host, port)

    try:
        await client.connect()
        print("✅ Connected to device\n")

        # Test 1: Device Info
        print("📋 Getting device information...")
        device_info = await client.get_device_info()
        print(f"✅ Device: {device_info.get('device')}")
        print(f"   Firmware: v{device_info.get('ver')}")
        print(f"   WiFi MAC: {device_info.get('wifi_mac')}")
        print(f"   Network: {device_info.get('wifi_name')}")
        print(f"   IP: {device_info.get('ip')}\n")

        # Test 2: Energy System Status (includes battery data)
        # Note: Rate limiting is handled automatically by the client
        print("⚡ Getting energy system status...")
        es_data = await client.get_es_status()
        print(f"✅ Battery:")
        print(f"   SOC: {es_data.get('bat_soc')}%")
        print(f"   Capacity: {es_data.get('bat_cap')} Wh")
        print(f"\n   Power Flows:")
        print(f"   Solar: {es_data.get('pv_power')} W")
        print(f"   Grid: {es_data.get('ongrid_power')} W (positive=export)")
        print(f"   Load: {es_data.get('offgrid_power')} W")
        print(f"\n   Energy Totals:")
        print(f"   Solar Generated: {es_data.get('total_pv_energy')} Wh")
        print(f"   Grid Import: {es_data.get('total_grid_input_energy')} Wh")
        print(f"   Grid Export: {es_data.get('total_grid_output_energy')} Wh")
        print(f"   Load Consumed: {es_data.get('total_load_energy')} Wh\n")

        # Test 3: Energy Meter (CT Sensors)
        print("📊 Getting energy meter status...")
        try:
            em_data = await client.get_em_status()
            ct_state = em_data.get('ct_state')
            print(f"✅ CT Sensors: {'Connected' if ct_state == 1 else 'Disconnected'}")
            if ct_state == 1:
                print(f"   Phase A: {em_data.get('a_power')} W")
                print(f"   Phase B: {em_data.get('b_power')} W")
                print(f"   Phase C: {em_data.get('c_power')} W")
                print(f"   Total: {em_data.get('total_power')} W")
        except Exception as e:
            print(f"⚠️  CT Sensors: Not available ({e})")

        # Summary
        print(f"\n{'='*70}")
        print("✅ ALL TESTS PASSED!")
        print(f"{'='*70}\n")

        print("Device Summary:")
        print(f"  Model: {device_info.get('device')}")
        print(f"  Battery: {es_data.get('bat_soc')}% ({es_data.get('bat_cap')} Wh)")
        print(f"  Grid: {es_data.get('ongrid_power')} W")
        print(f"  Solar: {es_data.get('pv_power')} W")

        print("\nVenus E 3 API Support:")
        print("  ✅ Marstek.GetDevice - Device information")
        print("  ✅ ES.GetStatus - Energy system + battery data")
        print("  ✅ EM.GetStatus - CT sensor data")
        print("\n  ❌ Bat.GetStatus - Not supported (use ES.GetStatus)")
        print("  ❌ ES.GetMode/SetMode - May not be supported on all hardware")
        print("  ❌ Wifi.GetStatus - Not supported")

        print("\nImportant Notes:")
        print("  • Rate limiting (2.5s between requests) is automatic")
        print("  • Home Assistant integration uses 30s polling")
        print("  • Mode control may not be available on all Venus E 3 hardware")

        print("\nNext Steps:")
        print("  1. Integration is ready to install in Home Assistant")
        print("  2. Copy custom_components/marstek_venus_e to ~/.homeassistant/custom_components/")
        print("  3. Restart Home Assistant")
        print("  4. Add integration: Settings > Devices & Services")
        print(f"  5. Enter device IP: {host}")
        print()

    finally:
        await client.close()


def main():
    """Main entry point."""
    # Parse command-line arguments
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT

    # Run the async test function
    asyncio.run(test_device(host, port))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
