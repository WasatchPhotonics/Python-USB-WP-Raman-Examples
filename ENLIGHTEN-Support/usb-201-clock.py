
import argparse
import time

from mcculw import ul
from mcculw.enums import InterfaceType, DigitalPortType, DigitalIODirection
from mcculw.device_info import DaqDeviceInfo

def time_ms():
    return 1000*time.time()

def config_first_detected_device(board_num, dev_id_list=None):
    """Adds the first available device to the UL.  If a types_list is specified,
    the first available device in the types list will be add to the UL.
    Parameters
    ----------
    board_num : int
        The board number to assign to the board when configuring the device.
    dev_id_list : list[int], optional
        A list of product IDs used to filter the results. Default is None.
        See UL documentation for device IDs.
    """
    ul.ignore_instacal()
    devices = ul.get_daq_device_inventory(InterfaceType.ANY)
    if not devices:
        raise Exception('Error: No DAQ devices found')

    print('Found', len(devices), 'DAQ device(s):')
    for device in devices:
        print('  ', device.product_name, ' (', device.unique_id, ') - ',
              'Device ID = ', device.product_id, sep='')

    device = devices[0]
    if dev_id_list:
        device = next((device for device in devices
                       if device.product_id in dev_id_list), None)
        if not device:
            err_str = 'Error: No DAQ device found in device ID list: '
            err_str += ','.join(str(dev_id) for dev_id in dev_id_list)
            raise Exception(err_str)

    # Add the first DAQ device to the UL with the specified board number
    ul.create_daq_device(board_num, device)

def start_clock(period, width):
    startTime = time_ms()

    signal_rise_counts = 0
    signal_fall_counts = 0

    while True:
        elapsed = time_ms() - startTime
        if elapsed // period > signal_rise_counts:
            # Send the value to the device
            ul.d_out(board_num, DigitalPortType.FIRSTPORTA, 0x1)
            signal_rise_counts = elapsed // period
        elif (elapsed - width) // period > signal_fall_counts:
            # Send the value to the device
            ul.d_out(board_num, DigitalPortType.FIRSTPORTA, 0x0)
            signal_fall_counts = (elapsed - width) // period

        # if you try to loop without sleep, the OS will add sleeping, decreasing accuracy
        time.sleep(1e-6)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog = "usb-201 clock",
        description = "generate a sequence of pulses at a regular timed interval"
    )
    parser.add_argument('-p', '--period-ms', dest="period", help="duration between pulse starts")
    parser.add_argument('-w', '--width-ms', dest="width", help="duration of pulses")
    args = parser.parse_args()

    board_num = 0
    config_first_detected_device(board_num, [])

    daq_dev_info = DaqDeviceInfo(board_num)
    if not daq_dev_info.supports_digital_io:
        raise Exception('Error: The DAQ device does not support digital output')
    
    print('\nActive DAQ device: ', daq_dev_info.product_name, ' (', daq_dev_info.unique_id, ')\n', sep='')

    dio_info = daq_dev_info.get_dio_info()

    # Find the first port that supports output, defaulting to None
    # if one is not found.
    port = next((port for port in dio_info.port_info if port.supports_output), None)

    if port is not None:
        # If the port is configurable, configure it for output
        if port.is_port_configurable:
            try:
                ul.d_config_port(board_num, port.type, DigitalIODirection.OUT)
            except ul.ULError as e:
                print('UL Error', e)

    start_clock(float(args.period), float(args.width))