# Philips AS111/12 time synchronization
# python as111.py '00:1D:DF:53:3C:1B' sync

# Get Bluetooth device
$device = Get-PnpDevice -Class Bluetooth -FriendlyName "PHILIPS AS111"

if ($?) {
    # Get device MAC address
    $deviceAddress = (Get-PnpDeviceProperty -InstanceId $device.InstanceId -KeyName 'DEVPKEY_Bluetooth_DeviceAddress').Data
    $mac = $deviceAddress.Insert(10,':').Insert(8,':').Insert(6,':').Insert(4,':').Insert(2,':')

    # Synchronize time
    Write-Host("Synchronizing time for", $device.FriendlyName, "($mac)")
    python as111.py $mac sync

} else {
    Write-Error('AS111 not available')
}
