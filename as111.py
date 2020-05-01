#!/usr/bin/python3
#
# MIT License
#
# Copyright (c) 2020 heckie75
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
#

from bluetooth import *
import datetime
import json
import sys




debug = 0
socket = None
sequence = 0
device = {
    "mac" : "",
    "name" : "",
    "version" : "",
    "datetime" : "",
    "volume" : 0,
    "capabilities" : {}
}

capabilities = ["0-VOLUME", "1-DSC", "2-DBB", "3-TREBLE", "4-BASS", 
                "5-FULL", "6-CHARGING", "7-BATTERY", "8-DATETIME", 
                "9-EQ1", "10-EQ2", "11-EQ3", "12-EQ4", "13-EQ5",
				"14-ALARM_VOLUME", "15-AC_DC_POWER_MODE", 
                "16-REMOTE_CONTROL", "17-FM_STATION_SEARCH", 
                "18-FM_FREQUENCY_TUNING", "19-FM_AUTO_PROGRAM", 
                "20-FM_MANUAL_PROGRAM", "21-FM_PRESET_STATION",
				"22-DOCK_ALARM_1", "23-DOCK_ALARM_2", 
                "24-DOCK_ALARM_LED", "25-AUDIO_SOURCE", "26-APPALM",
				"27-RCAPPSC" ]




def print_help():

    print("""
 USAGE:   as111.py <mac> [command]
 EXAMPLE: Set volume to 12
          $ ./as111.py vol 12

 vol <0-32>             Sets volume to value which is between 0 and 32
 mute                   Sets volume to 0
 alarm-led <off|on>    	Activates / deactivates alarm LED
 info                   Prints device info
 json                   Prints device info in JSON format
 debug                  Activates debug mode
 help                   Information about usage, commands and parameters
    """)




def print_info():

    print("""
MAC:     %s
Name:    %s
Version: %s
Time:    %s
Volume:  %i  
    """ % (device["mac"], device["name"], device["version"], device["datetime"], device["volume"]) )




def print_json():
    print(json.dumps(device, indent=2))
    



def connect():

    global socket

    if debug == 1:
        print("DEBUG: Connnect to %s" % device["mac"])

    try:
        client_socket = BluetoothSocket( RFCOMM )
        client_socket.connect((device["mac"], 1))
        client_socket.settimeout(2)

    except btcommon.BluetoothError as error:
        print("ERROR: %s" % error)
        print("ERROR: Connection failed! Check mac address and device.\n")
        exit(1)

    socket = client_socket

    if debug == 1:
        print("DEBUG: Connnected to %s" % device["mac"])




def disconnect():

    if debug == 1:
        print("DEBUG: disconnect")

    try:
        socket.close()

    except:
        pass

    if debug == 1:
        print("DEBUG: disconnected")




def send(data):

    raw = []

    if debug == 1:
        print("DEBUG: >>> %s" % (" ".join(str(i) for i in data)))

    try:
        socket.send(bytes(data))
        raw = list(socket.recv(255))

        if debug == 1:
            print("DEBUG: <<< %s" % (" ".join(str(i) for i in raw)))

    except btcommon.BluetoothError as error:
	    print("ERROR: request failed, %s" % error)

    return raw




def _get_request(command, payload = []):

    global sequence

    length = 3 + len(payload)
    sequence += 1
    request = [ 153, length, sequence, command ]

    checksum = command
    for p in payload:
        request += [ p ]
        checksum += p

    request += [ ( -1 * checksum ) & 255 ]

    return request




def get_timestamp_as_array():

    dt_now = datetime.datetime.now()

    cc  = dt_now.year // 100
    yy  = dt_now.year % 100
    mm  = dt_now.month - 1
    dd  = dt_now.day
    h24 = dt_now.hour
    m   = dt_now.minute
    s   = dt_now.second

    return [cc, yy, mm, dd, h24, m, s]




def _list_to_string(l):

    s = ""
    for c in l:
        s += chr(c) if c != 0 else ""

    return s




def request_device_info():

    # request device name
    if debug == 1:
        print("DEBUG: request device name")

    request = _get_request(8)
    raw = send(request)
    device["name"] = _list_to_string(raw)[4:-1]

    if debug == 1:
        print("DEBUG: device name is \"%s\"" % device["name"])

    # request device version
    if debug == 1:
        print("DEBUG: request device version")

    request = _get_request(19)
    raw = send(request)
    device["version"] = _list_to_string(raw)[4:-1]

    if debug == 1:
        print("DEBUG: device version is \"%s\"" % device["version"])

    # request device volume
    if debug == 1:
        print("DEBUG: request current volume")

    request = _get_request(15, [ 0 ])
    raw = send(request)
    device["volume"] = raw[-2]

    if debug == 1:
        print("DEBUG: current volume is %i" % device["volume"])

    # request device capabilities
    if debug == 1:
        print("DEBUG: request device capabilities")
        
    raw = send(_get_request(6))
    parse_capabilities(raw[8:-1])
    if debug == 1:
        print("DEBUG: device capabilities requested")




def parse_capabilities(caps):

    caps.reverse()
    supported = []
    i = 0

    for c in caps:
        for bit in range(0, 8):
            r = c >> (i % 8)
            if r & 1 == 1:
                supported += [ capabilities[i] ]
            i += 1

    device["capabilities"] = supported




def sync_time():

    ts = get_timestamp_as_array()
    ts_string = "%02d%02d-%02d-%02d %02d:%02d:%02d" % (ts[0], ts[1],
                                ts[2] + 1, ts[3], ts[4], ts[5], ts[6])

    if debug == 1:
        print("DEBUG: sync time to %s" % ts_string)

    send(_get_request(17, [ 8 ] + ts))

    device["datetime"] = ts_string

    if debug == 1:
        print("DEBUG: time synced")




def set_volume(vol):

    if debug == 1:
        print("DEBUG: Set volume to %i" % vol)
        
    raw = send(_get_request(17, [ 0, vol ]))

    if debug == 1:
        print("DEBUG: volume set to %i" % vol)




def set_alarm_led(status):

    if debug == 1:
        print("DEBUG: Set volume to %i" % vol)

    raw = send(_get_request(17, [ 24, status ]))

    if debug == 1:
        print("DEBUG: volume set to %i" % vol)



if __name__ == "__main__":

    if len(sys.argv) < 2:
        print_help()
        exit(1)

    if len(sys.argv) > 2 and sys.argv[2] == "debug":
        debug = 1

    device["mac"] = sys.argv[1]
    connect()

    request_device_info()
    sync_time()

    # process optional commands
    args = sys.argv[1:]
    while(len(args) > 0):
        command = args[0]
        args = args[1:]

        if command == "vol":
            try:
                vol = int(args[0]) % 32
            except:
                print("ERROR: Volume must be between 0 and 32")
                exit(1)
            set_volume(vol)
            args = args[1:]

        elif command == "mute":
            set_volume(0)

        elif command == "alarm-led":
            status = 1 if args[0] == "on" else 0
            set_alarm_led(status)
            args = args[1:]

        elif command == "info":
            print_info()

        elif command == "json":
            print_json()

        elif command == "help":
            print_help()

    disconnect()
    exit(0)