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

def get_value(bRequest, wValue, wIndex=0, lsb_len=4):
    # print(f">> ControlPacket(0x{DEVICE_TO_HOST:02x}, bRequest 0x{bRequest:02x}, wValue 0x{wValue:04x}, wIndex 0x{wIndex:04x}, len {lsb_len})")
    data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, lsb_len, TIMEOUT_MS)
    # print(f"<< {data}")
    value = 0
    for i in range(lsb_len):
        value |= (data[i] << i)
    # print(f"returning 0x{value:04x} ({value})")
    return value

def get_battery():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x13, 0, 3, TIMEOUT_MS)
    perc = data[1] + (1.0 * data[0] / 256.0)
    charging = 'charging' if data[2] else 'not charging'
    return f"{perc:5.2f}% ({charging})"

opcodes = { "SC_GET_BLE_INTF_MSG_RX_CNT"                : 0x38,
            "SC_GET_BLE_INTF_MSG_TX_CNT"                : 0x39,
            "SC_GET_BLE_INTF_KA_REQ_TX_CNT"             : 0x40,
            "SC_GET_BLE_INTF_KA_RESP_RX_CNT"            : 0x41,
            "SC_GET_BLE_INTF_BATT_INFO_REQ_RX_CNT"      : 0x42,
            "SC_GET_BLE_INTF_BATT_INFO_TX_CNT"          : 0x43,
            "SC_GET_BLE_INTF_UART_RESET_CNT"            : 0x44,
            "SC_GET_BLE_INTF_TOTAL_KEEP_ALIVE_TMO_CNT"  : 0x45,
            "SC_GET_BLE_INTF_B2B_KEEP_ALIVE_TMO_CNT"    : 0x46,
            "SC_GET_BLE_INTF_FPGA_REG_RD_REQ_RX_CNT"    : 0x47,
            "SC_GET_BLE_INTF_FPGA_REG_WR_REQ_RX_CNT"    : 0x48,
            "SC_GET_BLE_INTF_FPGA_REG_DATA_TX_CNT"      : 0x49,
            "SC_GET_BLE_INTF_EEPROM_PAGE_RD_REQ_RX_CNT" : 0x4a,
            "SC_GET_BLE_INTF_EEPROM_PAGE_DATA_TX_CNT"   : 0x4b }

print("%-45s: %s" % ("Timestamp", datetime.now()))
print("%-45s: %s" % ("Battery State", get_battery()))
for label, opcode in opcodes.items():
    print("%-45s: %d" % (label, get_value(0xff, opcode)))
print()
