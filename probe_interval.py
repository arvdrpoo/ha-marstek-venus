#!/usr/bin/env python3
"""Empirically probe the Marstek device's minimum request interval.

Sends a status command repeatedly at a series of fixed inter-request intervals
and reports success / packet loss / latency per interval. Requests are
sequential (one in flight at a time) over a connected UDP socket, matching the
integration's transport but WITHOUT its retry logic, so the numbers reflect raw
single-attempt device behaviour.

Pause the Home Assistant integration first: the device answers one request at a
time, so a running poll contends with the probe and inflates the loss.

Usage:
    python3 probe_interval.py [device_ip] [--port 30000]
                              [--intervals 2.5,1.0,0.5] [--count 100]
                              [--timeout 3.0] [--settle 5.0] [--method ES.GetStatus]

Reading the output: the fastest interval that still holds a low, stable loss is
a safe floor. A sharp jump in loss (or rising latency) means the interval is
too aggressive for this device/link.
"""
import argparse
import asyncio
import json
import socket
import statistics
import sys

DEFAULT_HOST = "192.168.1.194"
DEFAULT_PORT = 30000
DEFAULT_INTERVALS = [2.5, 2.0, 1.5, 1.0, 0.7, 0.5, 0.3, 0.2, 0.1]


async def one_request(sock, loop, req_id, method, timeout):
    """Send one request and wait for the matching reply; return latency in ms."""
    payload = json.dumps({"id": req_id, "method": method, "params": {"id": 0}}).encode()
    start = loop.time()
    await loop.sock_sendall(sock, payload)
    while True:
        remaining = timeout - (loop.time() - start)
        if remaining <= 0:
            raise asyncio.TimeoutError
        data = await asyncio.wait_for(loop.sock_recv(sock, 4096), timeout=remaining)
        try:
            msg = json.loads(data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        # Ignore stray/late replies for other ids (e.g. a prior timed-out request).
        if msg.get("id") == req_id:
            return (loop.time() - start) * 1000


async def probe(args):
    loop = asyncio.get_running_loop()
    print(
        f"Probing {args.host}:{args.port} — {args.method}, {args.count} reqs/interval, "
        f"{args.timeout}s timeout"
    )
    print("(Pause the Home Assistant integration first to avoid contention.)\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    sock.connect((args.host, args.port))

    # Preflight, tolerating a few dropped UDP packets.
    reached = False
    last_err = None
    for _ in range(5):
        try:
            await one_request(sock, loop, 1, args.method, args.timeout)
            reached = True
            break
        except (asyncio.TimeoutError, OSError) as err:
            last_err = err
            await asyncio.sleep(1.0)
    if not reached:
        print(f"UNREACHABLE: no response after 5 tries ({last_err!r}).")
        print("Confirm the device IP, that Open API is enabled in the app, that this host")
        print("is on the same LAN, and that HA (or another client) isn't holding the device.")
        sock.close()
        return 1
    print("Preflight OK: device is answering.\n")

    req_id = 1
    header = f"{'interval':>9} | {'ok':>3}/{'n':<4} | {'loss%':>5} | {'p50':>4} | {'p95':>4} | {'max':>5}"
    print(header)
    print("-" * len(header))
    for interval in args.intervals:
        await asyncio.sleep(args.settle)
        latencies, timeouts = [], 0
        for _ in range(args.count):
            cycle_start = loop.time()
            req_id = (req_id % 0xFFFF) + 1
            try:
                latencies.append(await one_request(sock, loop, req_id, args.method, args.timeout))
            except (asyncio.TimeoutError, OSError):
                timeouts += 1
            # Pace to the target interval, measured from this request's start.
            elapsed = loop.time() - cycle_start
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
        ok = len(latencies)
        loss = 100.0 * timeouts / args.count
        p50 = statistics.median(latencies) if latencies else float("nan")
        p95 = sorted(latencies)[int(len(latencies) * 0.95) - 1] if len(latencies) >= 2 else float("nan")
        mx = max(latencies) if latencies else float("nan")
        print(f"{interval:>9.2f} | {ok:>3}/{args.count:<4} | {loss:>5.1f} | {p50:>4.0f} | {p95:>4.0f} | {mx:>5.0f}")

    sock.close()
    return 0


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Probe the Marstek minimum request interval.")
    parser.add_argument("host", nargs="?", default=DEFAULT_HOST, help="Device IP address")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--intervals",
        type=lambda s: [float(x) for x in s.split(",")],
        default=DEFAULT_INTERVALS,
        help="Comma-separated inter-request intervals in seconds (default: full sweep)",
    )
    parser.add_argument("--count", type=int, default=20, help="Requests per interval")
    parser.add_argument("--timeout", type=float, default=3.0, help="Per-request timeout in seconds")
    parser.add_argument("--settle", type=float, default=5.0, help="Idle seconds between interval groups")
    parser.add_argument("--method", default="ES.GetStatus", help="JSON-RPC method to send")
    return parser.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])
    try:
        return asyncio.run(probe(args))
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 0


if __name__ == "__main__":
    sys.exit(main())
