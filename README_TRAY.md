# AS111 Tray Application

This is a system tray application for controlling Philips AS111 Bluetooth speakers with digital clock functionality.

## Features

- Sync time with the device
- Turn alarm LED on/off
- Set volume (0-32) or mute, with current volume displayed
- Start countdown (1-30 min, 45 min, 60 min)
- Start countup (1-30 min, 45 min, 60 min)
- Start displaying minutes and seconds (instead of normal clock)
- Set or unset alarm led
- Stop counting

## Requirements

- Python 3
- Bluetooth support (bluetoothctl on Linux, pyserial on Windows)
- Dependencies: `pip install -r requirements_tray.txt`

## Installation

1. Install Python dependencies:
   ```
   pip install -r requirements_tray.txt
   ```

2. Ensure Bluetooth is set up and the AS111 device is paired.

3. Run the tray application:
   ```
   python tray_app.py
   ```

The application will appear in the system tray. Right-click the icon to access the menu.

## Notes

- The application connects to the first available connected AS111 device.
- Long-running operations (countdown, countup) run in background threads.
- Current volume is displayed in the menu and updated when changed, but the menu may need to be reopened to see updates.
- Use "Stop Counting" to interrupt running countdowns or countups.

## Platforms

- Linux (with bluetoothctl)
- Windows (with pyserial for serial connections)