#!/usr/bin/env python3
#
# MIT License
#
# Copyright (c) 2020 heckie75
# Copyright (c) 2026 hobbe
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
macOS-only time synchronization for Philips AS111/12 Bluetooth docking station.

Requires: pip install pyobjc-framework-IOBluetooth
"""

import argparse
import datetime
import json
import subprocess
import sys
import time

if sys.platform != "darwin":
    sys.exit("ERROR: This script requires macOS.")

try:
    import objc
    from Foundation import NSObject
    from CoreFoundation import CFRunLoopRunInMode, kCFRunLoopDefaultMode
    from typing import Optional
    import IOBluetooth
except ImportError as exc:
    sys.exit(
        f"ERROR: Required PyObjC frameworks not found ({exc}).\n"
        "Install with:  pip install pyobjc-framework-IOBluetooth"
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PHILIPS_MAC_PREFIX = "00:1D:DF:"
RFCOMM_CHANNEL_ID = 1
PACKET_START_BYTE = 153
TIME_SYNC_COMMAND = 17
TIME_SYNC_RESPONSE_LEN = 6
RESPONSE_TIMEOUT_SECS = 2.0
RUNLOOP_STEP_SECS = 0.05

# kIOReturnSuccess (IOKit)
kIOReturnSuccess = 0

# Log levels
ERROR, WARN, INFO, DEBUG = 0, 1, 2, 3
_LEVEL_NAMES = ["ERROR", "WARN", "INFO", "DEBUG"]
_loglevel = ERROR

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def log(msg: str, level: int = INFO) -> None:
    if _loglevel >= level:
        print(f"{_LEVEL_NAMES[level]}:\t{msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# IOBluetooth RFCOMM delegate
# ---------------------------------------------------------------------------


class RFCOMMDelegate(NSObject):
    """Minimal IOBluetoothRFCOMMChannelDelegate that buffers incoming bytes."""

    def init(self):
        self = objc.super(RFCOMMDelegate, self).init()
        if self is None:
            return None
        self._buf = bytearray()
        self._channel_open = False
        return self

    def rfcommChannelOpenComplete_status_(self, channel, error):
        self._channel_open = error == kIOReturnSuccess
        log(f"rfcommChannelOpenComplete: error=0x{error:08X}, open={self._channel_open}", DEBUG)

    def rfcommChannelData_data_length_(self, channel, data, length):
        try:
            chunk = bytearray(data[:length])
            self._buf.extend(chunk)
            log(f"<<< received {length} byte(s): {' '.join(str(b) for b in chunk)}", DEBUG)
        except Exception as exc:
            log(f"Error reading incoming data: {exc}", WARN)

    def rfcommChannelClosed_(self, channel):
        log("rfcommChannelClosed", DEBUG)
        self._channel_open = False


# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------


def discover_mac(override: Optional[str] = None) -> str:
    """
    Return the Bluetooth MAC address of the first paired AS111 device.

    If override is given, return it directly (after uppercasing).
    Otherwise, parse `system_profiler SPBluetoothDataType -json`.
    """
    if override is not None:
        mac = override.upper()
        if not mac.startswith(PHILIPS_MAC_PREFIX):
            log(f"Provided MAC {mac} does not start with {PHILIPS_MAC_PREFIX} — proceeding anyway", WARN)
        log(f"Using provided MAC: {mac}", INFO)
        return mac

    log("Running system_profiler to discover AS111 device ...", DEBUG)
    try:
        result = subprocess.run(
            ["system_profiler", "SPBluetoothDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        sys.exit("ERROR: system_profiler timed out.")
    except FileNotFoundError:
        sys.exit("ERROR: system_profiler not found. Is this macOS?")

    if result.returncode != 0:
        sys.exit(f"ERROR: system_profiler failed (exit {result.returncode}).")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR: Could not parse system_profiler JSON: {exc}")

    bt_entries = data.get("SPBluetoothDataType", [])
    if not bt_entries:
        sys.exit("ERROR: No Bluetooth data in system_profiler output.")

    bt = bt_entries[0]

    # Search paired (connected and not-connected) device lists
    for section in ("device_connected", "device_not_connected"):
        for item in bt.get(section, []):
            for name, props in item.items():
                addr = props.get("device_address", "")
                if addr.upper().startswith(PHILIPS_MAC_PREFIX):
                    log(f"Found AS111 device: '{name}' at {addr}", INFO)
                    return addr.upper()

    sys.exit(
        f"ERROR: No Philips AS111 device (MAC prefix {PHILIPS_MAC_PREFIX}) found in paired "
        "Bluetooth devices.\nIs the device paired? Run: bluetooth-settings or System Settings > Bluetooth."
    )


# ---------------------------------------------------------------------------
# Protocol helpers
# ---------------------------------------------------------------------------

_sequence_counter = 0


def _next_sequence() -> int:
    global _sequence_counter
    _sequence_counter = (_sequence_counter + 1) & 0xFF
    return _sequence_counter


def build_packet(sequence: int, command: int, payload: list) -> bytes:
    """
    Build a wire packet:
      [153, length, sequence, command, *payload, checksum]
      length   = 3 + len(payload)
      checksum = (-1 * (command + sum(payload))) & 0xFF
    """
    length = 3 + len(payload)
    checksum = (-1 * (command + sum(payload))) & 0xFF
    packet = [PACKET_START_BYTE, length, sequence, command] + payload + [checksum]
    log(f">>> {' '.join(str(b) for b in packet)}", DEBUG)
    return bytes(packet)


def build_time_sync_packet() -> bytes:
    """Build the time-sync packet for the current local time."""
    now = datetime.datetime.now()
    cc        = now.year // 100
    yy        = now.year % 100
    mm_minus1 = now.month - 1   # protocol uses 0-indexed months
    dd        = now.day
    h24       = now.hour
    m         = now.minute
    s         = now.second

    ts_str = f"{cc:02d}{yy:02d}-{mm_minus1+1:02d}-{dd:02d} {h24:02d}:{m:02d}:{s:02d}"
    log(f"Syncing time to {ts_str}", INFO)

    payload = [8, cc, yy, mm_minus1, dd, h24, m, s]
    return build_packet(_next_sequence(), TIME_SYNC_COMMAND, payload)


# ---------------------------------------------------------------------------
# Main sync routine
# ---------------------------------------------------------------------------


def sync_time(mac: str) -> None:
    """
    Open an RFCOMM channel to the device, send the time-sync packet,
    wait for the 6-byte acknowledgement, then close the channel.
    """
    log(f"Looking up IOBluetoothDevice for {mac}", DEBUG)
    device = IOBluetooth.IOBluetoothDevice.deviceWithAddressString_(mac)
    if device is None:
        sys.exit(
            f"ERROR: IOBluetoothDevice.deviceWithAddressString_('{mac}') returned nil.\n"
            "Is the device paired?"
        )

    delegate = RFCOMMDelegate.alloc().init()

    log(f"Opening RFCOMM channel {RFCOMM_CHANNEL_ID} to {mac} ...", DEBUG)
    ret, channel = device.openRFCOMMChannelSync_withChannelID_delegate_(
        None, RFCOMM_CHANNEL_ID, delegate
    )

    if ret != kIOReturnSuccess or channel is None:
        sys.exit(
            f"ERROR: Failed to open RFCOMM channel (IOReturn=0x{ret:08X}).\n"
            "Is the device powered on and within Bluetooth range?"
        )
    log("RFCOMM channel open", DEBUG)

    try:
        packet = build_time_sync_packet()
        ret = channel.writeSync_length_(packet, len(packet))
        if ret != kIOReturnSuccess:
            sys.exit(f"ERROR: writeSync failed (IOReturn=0x{ret:08X}).")

        log(f"Packet sent, waiting up to {RESPONSE_TIMEOUT_SECS}s for response ...", DEBUG)

        # Spin the CoreFoundation run loop so IOBluetooth can deliver the
        # incoming response bytes to the delegate.
        deadline = time.monotonic() + RESPONSE_TIMEOUT_SECS
        while len(delegate._buf) < TIME_SYNC_RESPONSE_LEN:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                log(
                    f"Timed out waiting for response "
                    f"(received {len(delegate._buf)} of {TIME_SYNC_RESPONSE_LEN} bytes). "
                    "Time sync was likely applied by the device anyway.",
                    WARN,
                )
                break
            CFRunLoopRunInMode(kCFRunLoopDefaultMode, min(RUNLOOP_STEP_SECS, remaining), False)

        if len(delegate._buf) >= TIME_SYNC_RESPONSE_LEN:
            resp = list(delegate._buf[:TIME_SYNC_RESPONSE_LEN])
            log(f"<<< response: {' '.join(str(b) for b in resp)} ({len(resp)} bytes)", DEBUG)

    finally:
        log("Closing RFCOMM channel", DEBUG)
        channel.closeChannel()

    print(f"Time sync sent to {mac}.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize time to a Philips AS111/12 Bluetooth docking station (macOS only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                            # auto-detect AS111 via system_profiler
  %(prog)s --mac 00:1D:DF:52:F1:91   # explicit MAC address
  %(prog)s --verbose                  # INFO-level log output
  %(prog)s --debug                    # full DEBUG log output

Requirements:
  pip install pyobjc-framework-IOBluetooth
""",
    )
    parser.add_argument(
        "--mac",
        metavar="XX:XX:XX:XX:XX:XX",
        help="Bluetooth MAC address of the AS111 (skips auto-detection).",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="INFO-level log output.")
    parser.add_argument("--debug",   "-d", action="store_true", help="DEBUG-level log output.")
    return parser.parse_args()


def main() -> None:
    global _loglevel
    args = parse_args()

    if args.debug:
        _loglevel = DEBUG
    elif args.verbose:
        _loglevel = INFO

    mac = discover_mac(override=args.mac)
    sync_time(mac)


if __name__ == "__main__":
    main()
