#!/usr/bin/env python3
"""
Diagnostic script for Marstek Venus E UDP API troubleshooting.

This script provides detailed information about what's being sent
and received (or not received) to help diagnose connection issues.
"""
import asyncio
import json
import sys


class DiagnosticProtocol(asyncio.DatagramProtocol):
    """Protocol that logs everything for debugging."""

    def __init__(self):
        self.transport = None
        self.response_received = asyncio.Event()
        self.response_data = None

    def connection_made(self, transport):
        self.transport = transport
        print(f"✅ UDP socket created")
        print(f"   Local address: {transport.get_extra_info('sockname')}")
        print(f"   Remote address: {transport.get_extra_info('peername')}")

    def datagram_received(self, data, addr):
        print(f"\n📥 RECEIVED DATA from {addr}:")
        print(f"   Raw bytes ({len(data)} bytes): {data}")
        try:
            decoded = data.decode()
            print(f"   Decoded: {decoded}")
            parsed = json.loads(decoded)
            print(f"   Parsed JSON: {json.dumps(parsed, indent=2)}")
            self.response_data = parsed
        except Exception as e:
            print(f"   ⚠️  Failed to parse: {e}")
        self.response_received.set()

    def error_received(self, exc):
        print(f"\n❌ Protocol error: {exc}")

    def connection_lost(self, exc):
        if exc:
            print(f"\n❌ Connection lost: {exc}")


async def diagnose(host: str, port: int = 30000):
    """Run diagnostic checks."""
    print(f"\n{'='*70}")
    print(f"Marstek Venus E UDP API Diagnostics")
    print(f"{'='*70}\n")

    print(f"Target: {host}:{port}\n")

    # Create UDP endpoint
    loop = asyncio.get_event_loop()

    try:
        print("1. Creating UDP endpoint...")
        transport, protocol = await loop.create_datagram_endpoint(
            DiagnosticProtocol,
            remote_addr=(host, port)
        )

        print("\n2. Sending Marstek.GetDevice command...")
        request = {
            "id": 1,
            "method": "Marstek.GetDevice",
            "params": {"ble_mac": "0"}
        }
        request_json = json.dumps(request)
        request_bytes = request_json.encode()

        print(f"   Request JSON: {request_json}")
        print(f"   Request bytes ({len(request_bytes)} bytes): {request_bytes}")

        transport.sendto(request_bytes)
        print(f"   ✅ Data sent to {host}:{port}")

        print("\n3. Waiting for response (15 second timeout)...")
        print("   (Press Ctrl+C to stop waiting)\n")

        try:
            await asyncio.wait_for(protocol.response_received.wait(), timeout=15.0)
            print("\n✅ SUCCESS! Device responded!")
            if protocol.response_data:
                print("\nDevice Information:")
                result = protocol.response_data.get('result', {})
                for key, value in result.items():
                    print(f"   {key}: {value}")

        except asyncio.TimeoutError:
            print("\n❌ TIMEOUT - No response from device")
            print("\nPossible causes:")
            print("   1. Open API is NOT enabled in the Marstek mobile app")
            print("   2. Wrong UDP port (check app settings for configured port)")
            print("   3. Firewall blocking UDP traffic on port", port)
            print("   4. Device is on a different network segment")
            print("   5. Device firmware doesn't support the API")
            print("\nNext steps:")
            print("   1. Open the Marstek mobile app")
            print("   2. Go to device settings")
            print("   3. Enable 'Open API' or 'Local API' feature")
            print("   4. Note the UDP port number (default: 30000)")
            print("   5. Ensure port is between 49152-65535 for reliability")
            print("   6. Run this script again with correct port:")
            print(f"      python diagnose.py {host} <port>")

        transport.close()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*70}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python diagnose.py <device_ip> [port]")
        print("\nExample:")
        print("  python diagnose.py 192.168.1.195")
        print("  python diagnose.py 192.168.1.195 30000")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 30000

    try:
        asyncio.run(diagnose(host, port))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
