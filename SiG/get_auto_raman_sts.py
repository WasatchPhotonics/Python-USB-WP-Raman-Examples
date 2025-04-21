#!/usr/bin/env python

import sys
import usb.core
import time
import copy

from time import sleep

AUTO_RAMAN_TOP_LVL_FSM_STATE_IDLE = 1
AUTO_RAMAN_TOP_LVL_FSM_STATE_ACTIVATE_IMG_SNSR = 2
AUTO_RAMAN_TOP_LVL_FSM_STATE_WAIT_LASER_SWITCH_ON = 3
AUTO_RAMAN_TOP_LVL_FSM_STATE_WAIT_LASER_WARM_UP = 4
AUTO_RAMAN_TOP_LVL_FSM_STATE_CALC_INIT_SCALE_FACTOR = 5
AUTO_RAMAN_TOP_LVL_FSM_STATE_OPTIMIZATION = 6
AUTO_RAMAN_TOP_LVL_FSM_STATE_SPEC_AVG_WITH_LASER_ON = 7
AUTO_RAMAN_TOP_LVL_FSM_STATE_SPEC_AVG_WITH_LASER_OFF = 8
AUTO_RAMAN_TOP_LVL_FSM_STATE_DONE = 9
AUTO_RAMAN_TOP_LVL_FSM_STATE_ERROR = 10


AUTO_RAMAN_stateMapping = {
   AUTO_RAMAN_TOP_LVL_FSM_STATE_IDLE : "IDLE",
   AUTO_RAMAN_TOP_LVL_FSM_STATE_ACTIVATE_IMG_SNSR : "ACTIVATE IMG SNSR",
   AUTO_RAMAN_TOP_LVL_FSM_STATE_WAIT_LASER_SWITCH_ON : "WAIT LASER SW ON",
   AUTO_RAMAN_TOP_LVL_FSM_STATE_WAIT_LASER_WARM_UP : "WAIT LASER WARM UP",
   AUTO_RAMAN_TOP_LVL_FSM_STATE_CALC_INIT_SCALE_FACTOR : "CALC INIT SCALE FACTOR",
   AUTO_RAMAN_TOP_LVL_FSM_STATE_OPTIMIZATION : "OPTIMIZATION",
   AUTO_RAMAN_TOP_LVL_FSM_STATE_SPEC_AVG_WITH_LASER_ON : "AVG WITH LASER ON",
   AUTO_RAMAN_TOP_LVL_FSM_STATE_SPEC_AVG_WITH_LASER_OFF : "AVG WITH LASER OFF",
   AUTO_RAMAN_TOP_LVL_FSM_STATE_DONE : "DONE",
   AUTO_RAMAN_TOP_LVL_FSM_STATE_ERROR : "ERROR !!"
}

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

def get_auto_raman_proc_sts(p_d):
    # print("prev data ", p_d)
    data = Get_Value(0x94, 0x0, 8)
    # print("data :", data)
    respLen = data[0]
    topLvlFSMState = data[1]

    if (data != p_d):
        print("data :", data)
        if topLvlFSMState == AUTO_RAMAN_TOP_LVL_FSM_STATE_SPEC_AVG_WITH_LASER_ON \
           or topLvlFSMState == AUTO_RAMAN_TOP_LVL_FSM_STATE_SPEC_AVG_WITH_LASER_OFF:
           avgCnt = data[2]
           avgCnt <<= 8
           avgCnt |= data[3]
           acqCnt = data[4]
           acqCnt <<= 8
           acqCnt |= data[5]
           print("> state {}, acq # {} / avg cnt {}".format(AUTO_RAMAN_stateMapping[topLvlFSMState], acqCnt, avgCnt))
        elif topLvlFSMState == AUTO_RAMAN_TOP_LVL_FSM_STATE_OPTIMIZATION:
           loopIdx = data[2]
           loopIdx <<= 8
           loopIdx |= data[3]
           maxSigVal = data[4]
           maxSigVal <<= 8
           maxSigVal |= data[5]
           print("> state {}, loop-idx # {} / max sig lvl {}".format(AUTO_RAMAN_stateMapping[topLvlFSMState], loopIdx, maxSigVal))
        else:
           # print("Resp Len {}, Top Level FSM State {} / [{}]".format(respLen, topLvlFSMState, AUTO_RAMAN_stateMapping[topLvlFSMState]))
           print("> state {}".format(AUTO_RAMAN_stateMapping[topLvlFSMState]))
        print("")
    return data, topLvlFSMState

prev_data = []
while (1):
   prev_data, topState = get_auto_raman_proc_sts(prev_data)
   if topState == AUTO_RAMAN_TOP_LVL_FSM_STATE_IDLE \
      or topState == AUTO_RAMAN_TOP_LVL_FSM_STATE_DONE \
      or topState == AUTO_RAMAN_TOP_LVL_FSM_STATE_ERROR:
      break
   sleep(.01)
