#!/usr/bin/env python

import sys
import usb.core

import time
import datetime
from time import sleep

# BLE652 / nRF52832 message sequence charts
# https://infocenter.nordicsemi.com/topic/sdk_nrf5_v16.0.0/lib_dfu_transport_serial.html

# We are only upgrading the application. 
# Use nrfutil command to generate a DFU update package with two files (init file and binary file)
# The init file is the ".dat" file and it is around 72 bytes long.
#
# Example: 
# nrfutil pkg generate \
#          --application 170086_sig_ble_nrf_v4.3.1.hex \
#          --application-version-string "4.3.1" \
#          --hw-version 1  \
#          --app-boot-validation  VALIDATE_GENERATED_CRC  \
#          --sd-req 0xCB \
#          ble_dfu_image_v4.3.1.zip
#
#
# > The DFU controller sends the init packet and waits for the confirmation from the DFU 
#   target. 
# > DFU target validates the init packet and responds with the result. 
# > On successful validation, DFU controller sends the binary data.


# DFU Init packet 
# The DFU controller first checks if the init packet has already been transferred successfully. 
# If not, the DFU controller checks if it has been transferred partially. If some data has been 
# transferred already, the transfer is continued. Otherwise, the DFU controller sends a Create 
# command to create a new data object and then transfers the init packet. When the init packet 
# is available, the DFU controller issues an Execute command to initiate the validation of the 
# init packet.



BLE_DFU_OP_PROTOCOL_VERSION     = 0x00     # Retrieve protocol version.
BLE_DFU_OP_OBJECT_CREATE        = 0x01     # Create selected object.
BLE_DFU_OP_RECEIPT_NOTIF_SET    = 0x02     # Set receipt notification.
BLE_DFU_OP_CRC_GET              = 0x03     # Request CRC of selected object.
BLE_DFU_OP_OBJECT_EXECUTE       = 0x04     # Execute selected object.
BLE_DFU_OP_OBJECT_SELECT        = 0x06     # Select object.

BLE_DFU_OP_MTU_GET              = 0x07     # Retrieve MTU size.
BLE_DFU_OP_OBJECT_WRITE         = 0x08     # Write selected object.
BLE_DFU_OP_PING                 = 0x09     # Ping.
BLE_DFU_OP_HARDWARE_VERSION     = 0x0A     # Retrieve hardware version.
BLE_DFU_OP_FIRMWARE_VERSION     = 0x0B     # Retrieve firmware version.
BLE_DFU_OP_ABORT                = 0x0C     # Abort the DFU procedure.
BLE_DFU_OP_RESPONSE             = 0x60     # Response.
BLE_DFU_OP_INVALID              = 0xFF

SLIP_BYTE_END = 0xC0    # Indicates end of packet
SLIP_BYTE_ESC = 0xDB    # Indicates byte stuffing 
SLIP_BYTE_ESC_END = 0xDC    # ESC ESC_END means END data byte
SLIP_BYTE_ESC_ESC = 0xDD    # ESC ESC_ESC means ESC data byte 

BLE_DFU_RES_CODE_INVALID                 = 0x00    # Invalid opcode.
BLE_DFU_RES_CODE_SUCCESS                 = 0x01    # Operation successful.
BLE_DFU_RES_CODE_OP_CODE_NOT_SUPPORTED   = 0x02    # Opcode not supported.
BLE_DFU_RES_CODE_INVALID_PARAMETER       = 0x03    # Missing or invalid parameter value.
BLE_DFU_RES_CODE_INSUFFICIENT_RESOURCES  = 0x04    # Not enough memory for the data object.
BLE_DFU_RES_CODE_INVALID_OBJECT          = 0x05    # Data object does not match the firmware and 
                                                   # hardware requirements, the signature is wrong, 
                                                   # or parsing the command failed.
BLE_DFU_RES_CODE_UNSUPPORTED_TYPE        = 0x07    # Not a valid object type for a Create request.
BLE_DFU_RES_CODE_OPERATION_NOT_PERMITTED = 0x08    # The state of the DFU process does not allow 
                                                   # this operation.
BLE_DFU_RES_CODE_OPERATION_FAILED        = 0x0A    # Operation failed.
BLE_DFU_RES_CODE_EXT_ERROR               = 0x0B    # Extended error. The next byte of the response 
                                                   # contains the error code of the extended error 
                                                   # (see @ref nrf_dfu_ext_error_code_t.


BLE_DFU_OBJ_TYPE_INVALID   = 0x0   # Invalid object type.
BLE_DFU_OBJ_TYPE_COMMAND   = 0x1   # Command object.
BLE_DFU_OBJ_TYPE_DATA      = 0x2   # Data object.

BLE_DFU_MSG_TYPE_FIELD_SZ  = 1

BLE_DFU_RESP_RESULT_CODE_FIELD_SZ = 1

# MTU is uint16 sent in little endian order
BLE_DFU_MTU_FIELD_SZ = 2

BLE_DFU_MAX_SIZE_FIELD_SZ = 4
BLE_DFU_OFFSET_FIELD_SZ = 4
BLE_DFU_CRC32_FIELD_SZ = 4

BLE_DFU_GET_MTU_RESP_MSG_PYLD_SZ  = BLE_DFU_RESP_RESULT_CODE_FIELD_SZ + BLE_DFU_MTU_FIELD_SZ


BLE_DFU_OBJ_SEL_RESP_PYLD_LEN_SZ = BLE_DFU_RESP_RESULT_CODE_FIELD_SZ \
                                   + BLE_DFU_MAX_SIZE_FIELD_SZ \
                                   + BLE_DFU_OFFSET_FIELD_SZ \
                                   + BLE_DFU_CRC32_FIELD_SZ 

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

BLE_DFU_TX_MSG_TO_TGT = 0x8c
BLE_DFU_POLL_TGT = 0x8d

# Variables
BLE_DFU_tgtMTU = -1
BLE_DFU_maxSize = -1
BLE_DFU_offset = -1
BLE_DFU_crc32 = 0

dfuCmdGetMTU = [2,  BLE_DFU_OP_MTU_GET, SLIP_BYTE_END]
dfuCmdObjSel = [3,  BLE_DFU_OP_OBJECT_SELECT, 0x1, SLIP_BYTE_END]

def __dump(buff):
    print("\n------------------------------------------------------------------")
    print("Dumping buffer of len", len(buff))
    print("------------------------------------------------------------------")
    str = ""
    cnt = 0
    totCnt = 0
    for byte in buff:
        if cnt == 0:
            str += f"[{totCnt:#0{4}}]" + "  "
        str += f"{byte:#0{4}x}"
        str += "   "
        cnt += 1
        totCnt += 1
        if cnt == 8:
            print(str)
            str = ""
            cnt = 0
    print("\n------------------------------------------------------------------")

def __leTo32(inBuff):
    #print("leTo32 inbuff {}".format(inBuff))
    u32 = 0
    u32 = inBuff[3]
    u32 <<= 8
    u32 += inBuff[2]
    u32 <<= 8
    u32 += inBuff[1]
    u32 <<= 8
    u32 += inBuff[0]
    #print("leTo32 inbuff {}, u32 0x{:02x}".format(inBuff, u32))
    return u32

def ble_dfu_send_msg(txMsgBuff):
    print("Txing ble dfu msg of len {} ".format(len(txMsgBuff)))
    for byte in txMsgBuff:
        print("0x{:02x}".format(byte))
    dev.ctrl_transfer(HOST_TO_DEVICE, BLE_DFU_TX_MSG_TO_TGT, 0x0, 0x0, txMsgBuff) 
    print("Txd ...")

def ble_dfu_get_tgt_msg():
    print("\n\nSending poll request to tgt ...")
    raw = dev.ctrl_transfer(DEVICE_TO_HOST, BLE_DFU_POLL_TGT, 0x0, 0, 64, TIMEOUT_MS)
    msg = raw[1:].tolist()
    return msg
       

def ble_dfu_parse_resp(respMsg):
    print("Parsing response msg ... ", respMsg, " of len ", len(respMsg))
    respLen = len(respMsg)
    if respLen > 0:
       origReqType = respMsg[0]
       print("Orig Request Type : 0x{:02x}".format(origReqType))
       
       respLen -= BLE_DFU_MSG_TYPE_FIELD_SZ
       if origReqType == BLE_DFU_OP_OBJECT_SELECT:
          print("Rcvd response to OBJ SEL Request")
          if respLen >= BLE_DFU_OBJ_SEL_RESP_PYLD_LEN_SZ:
             rc = respMsg[1] 
             print("Result Code 0x{:02x}".format(rc))
             if rc == BLE_DFU_RES_CODE_SUCCESS:
                BLE_DFU_maxSize = __leTo32(respMsg[2:6])
                BLE_DFU_offset = __leTo32(respMsg[6:10])
                BLE_DFU_crc32 = __leTo32(respMsg[10:14])
                print("Max Sz {}, offset {}, CRC32 0x{:08x}".format(BLE_DFU_maxSize, BLE_DFU_offset, BLE_DFU_crc32))
             else:
                print("Response indicates error !! ")
          else:
             print("Response length < {}!!".format(BLE_DFU_OBJ_SEL_RESP_PYLD_LEN_SZ))


       if origReqType == BLE_DFU_OP_MTU_GET:
          print("Rcvd response to MTU GET Request")
          if respLen >= BLE_DFU_GET_MTU_RESP_MSG_PYLD_SZ:
             rc = respMsg[1] 
             print("Result Code 0x{:02x}".format(rc))
             if rc == BLE_DFU_RES_CODE_SUCCESS:
                BLE_DFU_tgtMTU = respMsg[3]
                BLE_DFU_tgtMTU <<= 8
                BLE_DFU_tgtMTU += respMsg[2]
                print("MTU is {} bytes", BLE_DFU_tgtMTU)
             else:
                print("Response indicates error !! ")
          else:       
             print("Response length < {}!!".format(BLE_DFU_GET_MTU_RESP_MSG_PYLD_SZ))
       
    else:
       print("Response too short !!")


def ble_dfu_parse_tgt_msg(msg):
    msgType = msg[0]
    print("\nParsing rcvd msg .. type 0x{:02x}".format(msgType))
    if msgType == BLE_DFU_OP_RESPONSE:
       ble_dfu_parse_resp(msg[1:])      
    else:
       print("Dropping msg !!")
    

def ble_dfu_get_resp():
  while (1):
    msg = ble_dfu_get_tgt_msg()
    if len(msg) == 0:
       print("No msg from tgt... ")
       sleep(1)
    else:
       print(datetime.datetime.now(), " : rcvd msg of len {} from tgt".format(len(msg)))
       idx = 0
       for i in msg:
           print("[{}] 0x{:02x}".format(idx, i))
           idx += 1
       ble_dfu_parse_tgt_msg(msg)
       break

# Read in the init file
BLE_DFU_initFileName = "170086_sig_ble_nrf_v4.3.1.dat"
with open(BLE_DFU_initFileName, mode='rb') as BLE_DFU_initFileObj: # b is important -> binary
    BLE_DFU_initFileData = list(BLE_DFU_initFileObj.read())

    __dump(BLE_DFU_initFileData)

quit()
    
print('-------------------------------------------------------')
ble_dfu_send_msg(dfuCmdGetMTU)
ble_dfu_get_resp()

print('-------------------------------------------------------')
ble_dfu_send_msg(dfuCmdObjSel)
ble_dfu_get_resp()

