#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
from PIL import Image, ImageDraw
import pystray
from as111 import AS111, log, INFO


class TrayApp:
    def __init__(self):
        self.as111 = AS111()
        self.connected_device = None
        self.current_volume = 0
        self.count_thread = None
        self.stop_counting = False

        # Connect to first available device
        devices = self.as111.get_connected_devices()
        if devices:
            self.connected_device = devices[0]
            self.as111.set_current_device(self.connected_device)
            self.current_volume = self.connected_device.get('volume', 0)
            log("Connected to device: %s" %
                self.connected_device['name'], INFO)

            self.sync_time_func()

        else:
            log("No connected devices found", INFO)

        # Create tray icon
        self.icon = self.create_icon()
        self.menu = self.create_menu()
        self.tray = pystray.Icon(
            "AS111 Tray", self.icon, "AS111 Control", self.menu)

    def create_icon(self):
        # Create a simple icon: a clock face
        image = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 54, 54), fill='blue')
        draw.ellipse((28, 28, 36, 36), fill='white')
        # Simple clock hands
        draw.line((32, 32, 32, 20), fill='black', width=2)  # hour
        draw.line((32, 32, 40, 32), fill='black', width=2)  # minute
        return image

    def create_menu(self):

        def create_vol_action(volume_level):
            return lambda icon, item: self.set_volume(volume_level)

        def create_countdown_action(minutes):
            return lambda icon, item: self.start_countdown(minutes, 0)

        def create_countup_action(minutes):
            return lambda icon, item: self.start_countup(minutes, 0)

        menu_items = []

        # Volume
        volume_menu_items = []
        volume_menu_items.append(pystray.MenuItem(
            "**Current: %d**" % self.current_volume, None, enabled=False))
        volume_menu_items.append(pystray.MenuItem("Mute", self.mute_volume))
        for vol in range(1, 33):
            volume_menu_items.append(pystray.MenuItem(
                text=str(vol),
                action=create_vol_action(vol)
            ))
        volume_menu = pystray.Menu(*volume_menu_items)
        menu_items.append(pystray.MenuItem("Volume", volume_menu))

        # Countdown
        countdown_menu_items = []
        for mins in range(1, 31):
            countdown_menu_items.append(pystray.MenuItem(
                "%d min" % mins, action=create_countdown_action(mins)))
        countdown_menu_items.append(pystray.MenuItem(
            "45 min", lambda _: self.start_countdown(45, 0)))
        countdown_menu_items.append(pystray.MenuItem(
            "60 min", lambda _: self.start_countdown(60, 0)))
        countdown_menu_items.append(pystray.MenuItem(
            "60 min", lambda _: self.start_countdown(90, 0)))
        countdown_menu = pystray.Menu(*countdown_menu_items)
        menu_items.append(pystray.MenuItem("Countdown", countdown_menu))

        # Countup
        countup_menu_items = []
        for mins in range(1, 31):
            countup_menu_items.append(pystray.MenuItem(
                "%d min" % mins, action=create_countup_action(mins)))
        countup_menu_items.append(pystray.MenuItem(
            "45 min", lambda _: self.start_countup(45, 0)))
        countup_menu_items.append(pystray.MenuItem(
            "60 min", lambda _: self.start_countup(60, 0)))
        countup_menu_items.append(pystray.MenuItem(
            "60 min", lambda _: self.start_countup(90, 0)))
        countup_menu = pystray.Menu(*countup_menu_items)
        menu_items.append(pystray.MenuItem("Countup", countup_menu))

        # mins and secs
        menu_items.append(pystray.MenuItem(
            "Minuntes and seconds", self.start_mins_n_secs))

        # Stop Countdown
        menu_items.append(pystray.MenuItem(
            "Stop Counting", self.stop_counting_func))

        # Alarm LED
        alarm_menu = pystray.Menu(
            pystray.MenuItem("On", self.alarm_led_on),
            pystray.MenuItem("Off", self.alarm_led_off)
        )
        menu_items.append(pystray.MenuItem("Alarm LED", alarm_menu))

        # Exit
        menu_items.append(pystray.MenuItem("Exit", self.exit_app))

        return pystray.Menu(*menu_items)

    def alarm_led_on(self, icon, item):
        if self.connected_device:
            threading.Thread(target=self._set_alarm_led, args=(1,)).start()

    def alarm_led_off(self, icon, item):
        if self.connected_device:
            threading.Thread(target=self._set_alarm_led, args=(0,)).start()

    def _set_alarm_led(self, status):
        self.as111.connect(self.connected_device['address'])
        self.as111.set_alarm_led(status)
        self.as111.disconnect()

    def mute_volume(self, icon, item):
        self.set_volume(0)

    def set_volume(self, vol):
        if self.connected_device:
            threading.Thread(target=self._set_volume, args=(vol,)).start()

    def _set_volume(self, vol):
        self.as111.connect(self.connected_device['address'])
        self.as111.set_volume(vol)
        self.as111.disconnect()

        self.current_volume = vol
        # Update menu - but pystray menu is static, so we need to recreate it
        self.update_menu()

    def start_countdown(self, minutes, seconds):
        if self.count_thread and self.count_thread.is_alive():
            return  # Already running
        self.stop_counting = False
        self.count_thread = threading.Thread(
            target=self._countdown, args=(minutes, seconds))
        self.count_thread.start()

    def _countdown(self, minutes, seconds):
        self.as111.clean_stop_signal()
        self.as111.connect(self.connected_device['address'])
        self.as111.set_alarm_led(1)
        self.as111.countdown(minutes, seconds, -1)
        self.as111.set_alarm_led(0)
        self.as111.sync_time()
        self.as111.disconnect()

    def start_mins_n_secs(self, icon, item):
        if self.count_thread and self.count_thread.is_alive():
            return  # Already running
        self.stop_counting = False
        self.count_thread = threading.Thread(
            target=self._mins_n_secs, args=(3600, ))
        self.count_thread.start()

    def _mins_n_secs(self, seconds):
        self.as111.clean_stop_signal()
        self.as111.connect(self.connected_device['address'])
        self.as111.set_alarm_led(1)
        self.as111.display_mins_n_secs(seconds)
        self.as111.set_alarm_led(0)
        self.as111.sync_time()
        self.as111.disconnect()

    def stop_counting_func(self, icon, item):
        self.stop_counting = True
        self.as111.set_stop_signal()

    def sync_time_func(self):
        self.as111.connect(self.connected_device['address'])
        self.as111.sync_time()
        self.as111.disconnect()

    def start_countup(self, minutes, seconds):
        if self.count_thread and self.count_thread.is_alive():
            return
        self.stop_countdown = False  # Reuse the flag
        self.count_thread = threading.Thread(
            target=self._countup, args=(minutes, seconds))
        self.count_thread.start()

    def _countup(self, minutes, seconds):
        self.as111.clean_stop_signal()
        self.as111.connect(self.connected_device['address'])
        self.as111.set_alarm_led(1)
        # countup is countdown with step=1
        self.as111.countdown(minutes, seconds, 1)
        self.as111.sync_time()
        self.as111.set_alarm_led(0)
        self.as111.disconnect()

    def update_menu(self):
        # Recreate menu with updated volume
        self.menu = self.create_menu()
        self.tray.menu = self.menu

    def exit_app(self, icon, item):
        self.stop_countdown = True
        self.as111.set_stop_signal()
        self.sync_time_func()
        icon.stop()


if __name__ == "__main__":
    app = TrayApp()
    app.tray.run()
