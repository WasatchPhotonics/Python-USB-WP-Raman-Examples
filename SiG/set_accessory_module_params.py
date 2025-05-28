#!/usr/bin/env python
import sys
import usb.core
import argparse

SC_ACC_MODULE_CONT_PROBE_PERIOD_SET_REQ = 0x98
SC_ACC_MODULE_CONT_PROBE_WIDTH_SET_REQ = 0x99
SC_ACC_MODULE_CONT_PROBE_DELAY_SET_REQ = 0x9a
SC_ACC_MODULE_CONT_PROBE_RPT_CNT_SET_REQ = 0x9b

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def set_acc_mod_cont_strobe_width_usecs(widthUsecs):
    buff = bytearray()
   
    byte = widthUsecs & 0xff
    buff.append(byte)
  
    byte = ((widthUsecs >> 8) & 0xff)
    buff.append(byte)
   
    byte = ((widthUsecs >> 16) & 0xff)
    buff.append(byte)

    byte = ((widthUsecs >> 24) & 0xff)
    buff.append(byte)
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, SC_ACC_MODULE_CONT_PROBE_WIDTH_SET_REQ, 0, buff, TIMEOUT_MS)


def set_acc_mod_cont_strobe_delay_usecs(dlyUsecs):
    buff = bytearray()
   
    byte = dlyUsecs & 0xff
    buff.append(byte)
  
    byte = ((dlyUsecs >> 8) & 0xff)
    buff.append(byte)
   
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, SC_ACC_MODULE_CONT_PROBE_DELAY_SET_REQ, 0, buff, TIMEOUT_MS)


def set_acc_mod_cont_strobe_rpt_cnt(rptCnt):
    buff = bytearray()
   
    byte = rptCnt & 0xff
    buff.append(byte)
  
    byte = ((rptCnt >> 8) & 0xff)
    buff.append(byte)
   
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, SC_ACC_MODULE_CONT_PROBE_RPT_CNT_SET_REQ, 0, buff, TIMEOUT_MS)


def set_acc_mod_cont_strobe_period_usecs(periodUsecs):
    cmd = 0xff
    buff = bytearray()
   
    byte = periodUsecs & 0xff
    buff.append(byte)
  
    byte = ((periodUsecs >> 8) & 0xff)
    buff.append(byte)
   
    byte = ((periodUsecs >> 16) & 0xff)
    buff.append(byte)

    byte = ((periodUsecs >> 24) & 0xff)
    buff.append(byte)

    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, SC_ACC_MODULE_CONT_PROBE_PERIOD_SET_REQ, 0, buff, TIMEOUT_MS)


set_acc_mod_cont_strobe_period_usecs(7891234)
set_acc_mod_cont_strobe_width_usecs(25010)
set_acc_mod_cont_strobe_delay_usecs(62355)
set_acc_mod_cont_strobe_rpt_cnt(1278)
