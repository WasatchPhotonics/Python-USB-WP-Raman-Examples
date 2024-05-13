#!/usr/bin/env python

import sys
import usb.core
from datetime import datetime

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def get_uint(bRequest, wValue, wIndex=0, lsb_len=4):
    # print(f">> ControlPacket(0x{DEVICE_TO_HOST:02x}, bRequest 0x{bRequest:02x}, wValue 0x{wValue:04x}, wIndex 0x{wIndex:04x}, len {lsb_len})")
    data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, lsb_len, TIMEOUT_MS)
    # print(f"<< {data}")
    value = 0
    for i in range(lsb_len):
        value |= (data[i] << i)
    # print(f"returning 0x{value:04x} ({value})")
    return value

def get_string(bRequest, wValue, wIndex=0, length=32):
    data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, length, TIMEOUT_MS)
    s = ""
    for c in data:
        if c == 0:
            break
        s += chr(c)
    return s

def get_battery():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x13, 0, 3, TIMEOUT_MS)
    perc = data[1] + (1.0 * data[0] / 256.0)
    charging = 'charging' if data[2] else 'not charging'
    return f"{perc:5.2f}% ({charging})"

def get_firmware_version():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xc0, 0, 0, 4, TIMEOUT_MS)
    return ".".join([str(d) for d in reversed(data)])

def get_fpga_version():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xb4, 0, 0, 7, TIMEOUT_MS)
    return "".join([chr(c) for c in data])

report = { "Timestamp"                                 : datetime.now(),
           "Battery State"                             : get_battery(),
           "Microcontroller FW Version"                : get_firmware_version(),
           "FPGA FW Version"                           : get_fpga_version(),
           "BLE FW Version"                            : get_string(0xff, 0x2d),
           "BLE IC Partnumber"                         : get_string(0xff, 0x2e),
           "BLE Radio State"                           : get_uint(0xff, 0x2f, lsb_len=1),
           "GET_BLE_INTF_MSG_RX_CNT"                   : get_uint(0xff, 0x38),
           "GET_BLE_INTF_MSG_TX_CNT"                   : get_uint(0xff, 0x39),
           "GET_BLE_INTF_KA_REQ_TX_CNT"                : get_uint(0xff, 0x40),
           "GET_BLE_INTF_KA_RESP_RX_CNT"               : get_uint(0xff, 0x41),
           "GET_BLE_INTF_BATT_INFO_REQ_RX_CNT"         : get_uint(0xff, 0x42),
           "GET_BLE_INTF_BATT_INFO_TX_CNT"             : get_uint(0xff, 0x43),
           "GET_BLE_INTF_UART_RESET_CNT"               : get_uint(0xff, 0x44),
           "GET_BLE_INTF_TOTAL_KEEP_ALIVE_TMO_CNT"     : get_uint(0xff, 0x45),
           "GET_BLE_INTF_B2B_KEEP_ALIVE_TMO_CNT"       : get_uint(0xff, 0x46),
           "GET_BLE_INTF_FPGA_REG_RD_REQ_RX_CNT"       : get_uint(0xff, 0x47),
           "GET_BLE_INTF_FPGA_REG_WR_REQ_RX_CNT"       : get_uint(0xff, 0x48),
           "GET_BLE_INTF_FPGA_REG_DATA_TX_CNT"         : get_uint(0xff, 0x49),
           "GET_BLE_INTF_EEPROM_PAGE_RD_REQ_RX_CNT"    : get_uint(0xff, 0x4a),
           "GET_BLE_INTF_EEPROM_PAGE_DATA_TX_CNT"      : get_uint(0xff, 0x4b) }

for label, value in report.items():
    print("%-45s: %s" % (label, value))

print()
