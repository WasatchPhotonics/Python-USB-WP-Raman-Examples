#!/usr/bin/env python

import sys
import usb.core

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def get_value(bRequest, wValue, wIndex=0, lsb_len=2):
    print(f">> ControlPacket(0x{DEVICE_TO_HOST:02x}, bRequest 0x{bRequest:02x}, wValue 0x{wValue:04x}, wIndex 0x{wIndex:04x}, len {lsb_len})")
    data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, lsb_len, TIMEOUT_MS)
    print(f"<< {data}")
    value = 0
    for i in range(lsb_len):
        value |= (data[i] << i)
    print(f"returning 0x{value:04x} ({value})")

# Per Ram:
# 0xff, 0x40 gives you count of keep alive requests sent by STM32 to BLE
# 0xff, 0x41 gives you count of keep alive responses received by STM32 from BLE
# 0xff, 0x38 gives total cnt of messages received by STM32 over the UART link with BLE
# 0xff, 0x39 gives total cnt of messages transmitted by STM32 over the UART link with BLE

battery_state = get_value(0xff, 0x13, lsb_len=3)
print(f"Battery State: {battery_state}")

stm_to_ble_keepalive_cnt = get_value(0xff, 0x40)
ble_to_stm_keepalive_cnt = get_value(0xff, 0x41)
stm_uart_msg_rx_cnt      = get_value(0xff, 0x38)
stm_uart_msg_tx_cnt      = get_value(0xff, 0x39)

print(f"STM-to-BLE Keepalive Count: {stm_to_ble_keepalive_cnt}")
print(f"BLE-to-STM Keepalive Count: {ble_to_stm_keepalive_cnt}")
print(f"STM Rx UART Msg Count:      {stm_uart_msg_rx_cnt}")
print(f"STM Tx UART Msg Count:      {stm_uart_msg_rx_cnt}")
