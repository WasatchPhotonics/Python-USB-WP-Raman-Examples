#!/usr/bin/env python

import sys
import usb.core
import argparse
import zlib
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

SLIP_RX_STATE_ESC_RCVD = 1
SLIP_RX_STATE_DECODING = 2


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


BLE_DFU_errCodeMap = {
  BLE_DFU_RES_CODE_INVALID : "Invalid opcode",
  BLE_DFU_RES_CODE_SUCCESS : "Operation successful",
  BLE_DFU_RES_CODE_OP_CODE_NOT_SUPPORTED : "Opcode not supported",
  BLE_DFU_RES_CODE_INVALID_PARAMETER : "Missing or invalid parameter value",
  BLE_DFU_RES_CODE_INSUFFICIENT_RESOURCES : "Not enough memory for the data object",
  BLE_DFU_RES_CODE_INVALID_OBJECT : "Data object does not match fw and hw reqs, wrong signature, or cmd parsing flr",
  BLE_DFU_RES_CODE_UNSUPPORTED_TYPE : "Not a valid object type for a Create request",
  BLE_DFU_RES_CODE_OPERATION_NOT_PERMITTED : "The state of the DFU process does not allow this operation",
  BLE_DFU_RES_CODE_OPERATION_FAILED : "Operation failed",
}


# Field in firmware version request message
BLE_DFU_FW_TYPE_BOOT_LOADER_IMAGE_NR  = 0
BLE_DFU_FW_TYPE_SOFT_DEVICE_IMAGE_NR  = 1
BLE_DFU_FW_TYPE_APPLICATION_IMAGE_NR  = 2

# Field in firmware version resp message
BLE_DFU_FIRMWARE_TYPE_SOFTDEVICE    = 0x00
BLE_DFU_FIRMWARE_TYPE_APPLICATION   = 0x01
BLE_DFU_FIRMWARE_TYPE_BOOTLOADER    = 0x02
BLE_DFU_FIRMWARE_TYPE_UNKNOWN       = 0xFF


###########################################################################################################################################
# Extended Error Codes
###########################################################################################################################################
BLE_DFU_EXT_ERROR_NO_ERROR = 0x00              # No extended error code has been set. This error indicates an implementation problem. 

BLE_DFU_EXT_ERROR_INVALID_ERROR_CODE = 0x01    # Invalid error code. This error code should never be used outside of development. 

BLE_DFU_EXT_ERROR_WRONG_COMMAND_FORMAT = 0x02  # The format of the command was incorrect. This error code is not used in the
                                               # current implementation, because @ref NRF_DFU_RES_CODE_OP_CODE_NOT_SUPPORTED
                                               # and @ref NRF_DFU_RES_CODE_INVALID_PARAMETER cover all
                                               # possible format errors.

BLE_DFU_EXT_ERROR_UNKNOWN_COMMAND = 0x03       # The command was successfully parsed, but it is not supported or unknown. 

BLE_DFU_EXT_ERROR_INIT_COMMAND_INVALID = 0x04  # The init command is invalid. The init packet either has
                                               # an invalid update type or it is missing required fields for the update type
                                               # (for example, the init packet for a SoftDevice update is missing the SoftDevice size field).

BLE_DFU_EXT_ERROR_FW_VERSION_FAILURE = 0x05    # The firmware version is too low. For an application or SoftDevice, the version must be greater than
                                               # or equal to the current version. For a bootloader, it must be greater than the current version.
                                               # to the current version. This requirement prevents downgrade attacks.

BLE_DFU_EXT_ERROR_HW_VERSION_FAILURE = 0x06    # The hardware version of the device does not match the required
                                               # hardware version for the update.

BLE_DFU_EXT_ERROR_SD_VERSION_FAILURE = 0x07    # The array of supported SoftDevices for the update does not contain
                                               # the FWID of the current SoftDevice or the first FWID is '0' on a
                                               # bootloader which requires the SoftDevice to be present.

BLE_DFU_EXT_ERROR_SIGNATURE_MISSING = 0x08     # The init packet does not contain a signature. This error code is not used in the
                                               # current implementation, because init packets without a signature
                                               # are regarded as invalid.

BLE_DFU_EXT_ERROR_WRONG_HASH_TYPE = 0x09      # The hash type that is specified by the init packet is not supported by the DFU bootloader.
BLE_DFU_EXT_ERROR_HASH_FAILED = 0x0A          # The hash of the firmware image cannot be calculated. 
BLE_DFU_EXT_ERROR_WRONG_SIGNATURE_TYPE = 0x0B # The type of the signature is unknown or not supported by the DFU bootloader.
BLE_DFU_EXT_ERROR_VERIFICATION_FAILED = 0x0C  # The hash of the received firmware image does not match the hash in the init packet.
BLE_DFU_EXT_ERROR_INSUFFICIENT_SPACE = 0x0D   # The available space on the device is insufficient to hold the firmware.
###########################################################################################################################################


BLE_DFU_extErrCodeMap = {
  BLE_DFU_EXT_ERROR_NO_ERROR : "No extended error code set",
  BLE_DFU_EXT_ERROR_INVALID_ERROR_CODE : "Invalid error code",
  BLE_DFU_EXT_ERROR_WRONG_COMMAND_FORMAT :  "The format of the command is incorrect",
  BLE_DFU_EXT_ERROR_UNKNOWN_COMMAND : "Command parsed successfully, but it is unsupported or unknown",
  BLE_DFU_EXT_ERROR_INIT_COMMAND_INVALID : "Init cmd has invalid update type or missing required fields",
  BLE_DFU_EXT_ERROR_FW_VERSION_FAILURE : "The firmware version is too low.",
  BLE_DFU_EXT_ERROR_HW_VERSION_FAILURE : "Hardware version mismatch",
  BLE_DFU_EXT_ERROR_SD_VERSION_FAILURE : "SoftDevice version mismatch",
  BLE_DFU_EXT_ERROR_SIGNATURE_MISSING : "The init packet does not contain a signature",
  BLE_DFU_EXT_ERROR_WRONG_HASH_TYPE : "Unsupported hash type in the init packet",
  BLE_DFU_EXT_ERROR_HASH_FAILED : "Firmware image hash could not be calculated",
  BLE_DFU_EXT_ERROR_WRONG_SIGNATURE_TYPE : "Signature type is unknown or not supported",
  BLE_DFU_EXT_ERROR_VERIFICATION_FAILED : "Firmware image hash mismatch with hash in init packet",
  BLE_DFU_EXT_ERROR_INSUFFICIENT_SPACE :  "Insufficient space for holding firmware image"
}

BLE_DFU_OBJ_TYPE_INVALID   = 0x0   # Invalid object type.
BLE_DFU_OBJ_TYPE_COMMAND   = 0x1   # Command object.
BLE_DFU_OBJ_TYPE_DATA      = 0x2   # Data object.

BLE_DFU_MSG_TYPE_FIELD_SZ  = 1

BLE_DFU_RESP_RESULT_CODE_FIELD_SZ = 1
BLE_DFU_RESP_RESULT_EXTENDED_CODE_FIELD_SZ = 1

# MTU is uint16 sent in little endian order
BLE_DFU_MTU_FIELD_SZ = 2

BLE_DFU_MAX_SIZE_FIELD_SZ = 4
BLE_DFU_OFFSET_FIELD_SZ = 4
BLE_DFU_CRC32_FIELD_SZ = 4
BLE_DFU_FW_TYPE_FIELD_SZ = 1
BLE_DFU_FW_START_ADDR_FIELD_SZ = 4
BLE_DFU_FW_SIZE_FIELD_SZ = 4
BLE_DFU_FW_VERSION_FIELD_SZ = 4  # Version info in the format xx.yy.zz is converted to 
                                 # 4 byte integer with value xx * 10000 + yy * 100 + zz
                                 # For example: 4.3.1 => 4*10000 + 3*100 + 1 = 40301

BLE_DFU_FW_VER_RESP_PYLD_SZ = BLE_DFU_RESP_RESULT_CODE_FIELD_SZ \
                              + BLE_DFU_FW_TYPE_FIELD_SZ \
                              + BLE_DFU_FW_VERSION_FIELD_SZ \
                              + BLE_DFU_FW_START_ADDR_FIELD_SZ \
                              + BLE_DFU_FW_SIZE_FIELD_SZ

BLE_DFU_OBJ_EXEC_RESP_PYLD_SZ = BLE_DFU_RESP_RESULT_CODE_FIELD_SZ

BLE_DFU_GET_MTU_RESP_MSG_PYLD_SZ  = BLE_DFU_RESP_RESULT_CODE_FIELD_SZ + BLE_DFU_MTU_FIELD_SZ

BLE_DFU_GET_CRC_RESP_PYLD_SZ = BLE_DFU_RESP_RESULT_CODE_FIELD_SZ \
                               + BLE_DFU_OFFSET_FIELD_SZ \
                               + BLE_DFU_CRC32_FIELD_SZ

BLE_DFU_OBJ_SEL_RESP_PYLD_SZ = BLE_DFU_RESP_RESULT_CODE_FIELD_SZ \
                               + BLE_DFU_MAX_SIZE_FIELD_SZ \
                               + BLE_DFU_OFFSET_FIELD_SZ \
                               + BLE_DFU_CRC32_FIELD_SZ 

BLE_DFU_OBJ_CREATE_RESP_PYLD_LEN_SZ = BLE_DFU_RESP_RESULT_CODE_FIELD_SZ

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

BLE_DFU_TX_MSG_TO_TGT = 0x8c
BLE_DFU_POLL_TGT = 0x8d

# Variables
BLE_DFU_tgtInitPktValid = False


# Local error codes
BLE_DFU_RC_FAILURE = 0
BLE_DFU_RC_SUCCESS = 1
BLE_DFU_RC_NO_RESPONSE = 2
BLE_DFU_RC_TIMED_OUT = 3
BLE_DFU_RC_RCVD_MSG_TOO_SHORT = 4
BLE_DFU_RC_INIT_PACKET_TRANSFER_ERROR = 5
BLE_DFU_RC_INIT_FILE_CRC32_MISMATCH = 6
BLE_DFU_RC_DATA_OBJ_TRANSFER_ERROR = 5
BLE_DFU_RC_DATA_OBJ_CRC32_MISMATCH = 6
BLE_DFU_RC_SLIP_DECODE_FLR = 7
BLE_DFU_RC_TGT_APP_FW_OFFSET_INVALID = 8
BLE_DFU_RC_PARTIAL_SUCCESS = 9
BLE_DFU_RC_TGT_RESP_ERROR_BASE = 128
BLE_DFU_RC_TGT_RESP_EXTENDED_ERROR_BASE = 256

BLE_DFU_RC_TGT_RESP_ERROR_BASE

BLE_DFU_objExecCmdMsg = [2, BLE_DFU_OP_OBJECT_EXECUTE, SLIP_BYTE_END]
BLE_DFU_getMTUMsg =  [2, BLE_DFU_OP_MTU_GET, SLIP_BYTE_END]
BLE_DFU_objSelMsg =  [3, BLE_DFU_OP_OBJECT_SELECT, 0xff, SLIP_BYTE_END]
BLE_DFU_createObjReqMsg = [7,  BLE_DFU_OP_OBJECT_CREATE, 0xff, 0, 0, 0, 0, SLIP_BYTE_END]
BLE_DFU_getCRCReqMsg = [2, BLE_DFU_OP_CRC_GET, SLIP_BYTE_END] 
BLE_DFU_execReqMsg = [2, BLE_DFU_OP_OBJECT_EXECUTE, SLIP_BYTE_END]
BLE_DFU_abortReqMsg = [2, BLE_DFU_OP_ABORT, SLIP_BYTE_END]
BLE_DFU_fwVerReqMsg = [3, BLE_DFU_OP_FIRMWARE_VERSION, BLE_DFU_FW_TYPE_APPLICATION_IMAGE_NR, SLIP_BYTE_END]


BLE_DFU_MAX_SLIP_PDU_LEN = 64 - 1


def __dump(buff):
    print("------------------------------------------------------------------")
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
    if cnt > 0:
       print(str)
    print("------------------------------------------------------------------")



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



def __calcCRC32(inBuff):
    crc32 = zlib.crc32(inBuff)
    if args.debug:
       print("Calc CRC32 is 0x{:08x}".format(crc32))
    return crc32 



def ble_dfu_send_msg(txMsgBuff):
    if args.debug:
       print("Txing ble dfu msg of len {} ".format(len(txMsgBuff)))
    if args.debug:
       __dump(txMsgBuff)
    dev.ctrl_transfer(HOST_TO_DEVICE, BLE_DFU_TX_MSG_TO_TGT, 0x0, 0x0, txMsgBuff) 
    if args.debug:
       print("Txd ...")


def ble_dfu_get_tgt_msg():
    if args.debug:
       print("Sending poll request to tgt ...")
    raw = dev.ctrl_transfer(DEVICE_TO_HOST, BLE_DFU_POLL_TGT, 0x0, 0, 64, TIMEOUT_MS)
    msg = raw[1:].tolist()
    return msg



def SLIP_decodeMsg(inBuff):
    decState = SLIP_RX_STATE_DECODING
    outBuff = []

    for byte in inBuff:
        if decState == SLIP_RX_STATE_DECODING:
           if byte == SLIP_BYTE_END:
              if args.debug:
                 print("SLIP_dec(): fnd EOP :-)")
              break
           else:
              if byte == SLIP_BYTE_ESC:
                 decState = SLIP_RX_STATE_ESC_RCVD
              else:
                 outBuff += [byte]
        else:
           if decState == SLIP_RX_STATE_ESC_RCVD:
              if byte == SLIP_BYTE_ESC_END:
                 outBuff += [SLIP_BYTE_END]
                 decState = SLIP_RX_STATE_DECODING
              else:
                 if byte == SLIP_BYTE_ESC_ESC:
                    outBuff += [SLIP_BYTE_ESC]
                    decState = SLIP_RX_STATE_DECODING
                 else:
                    # Protocol violation
                    print("SLIP_dec(): proto violation fnd !!")
                    outBuff = []
                    break
        # print("SLIP_dec(): byte 0x{:02x}".format(byte))
        # _dump(outBuff)

    if args.debug:
       print("Encoded Buff sz {}, decoded buff sz {}".format(len(inBuff), len(outBuff)))
    return outBuff



def SLIP_encodeChunk(msgType, inBuff, maxEncSz):

    outBuff = [msgType]
    inOffset = 0
    spaceLeft = maxEncSz - 1 - 1  # for the message type byte and the terminating byte

    if args.debug:
       print("\nIn Buffer max enc sz {} bytes".format(maxEncSz))
    # __dump(inBuff)

    bytesAddedCnt = 0
    for inByte in inBuff:
        # print("in-off {}, byte 0x{:02x}, added {}, space left {}".format(inOffset, inByte, bytesAddedCnt, spaceLeft))

        if inByte == SLIP_BYTE_END:
           if spaceLeft < 2:
              if args.debug:
                 print("No space left ... ")
              break

           outBuff += [SLIP_BYTE_ESC]
           outBuff += [SLIP_BYTE_ESC_END]
           spaceLeft -= 2
           bytesAddedCnt += 2
        
        else:
           if inByte == SLIP_BYTE_ESC:
              if spaceLeft < 2:
                 if args.debug:
                    print("No space left ... ")
                 break

              outBuff += [SLIP_BYTE_ESC]
              outBuff += [SLIP_BYTE_ESC_ESC]
              spaceLeft -= 2
              bytesAddedCnt += 2
           else:
              if spaceLeft < 1:
                 if args.debug:
                    print("No space left ... ")
                 break

              outBuff += [inByte]
              spaceLeft -= 1
              bytesAddedCnt += 1

        inOffset += 1

        # Looks like number of bytes to write to flash has to be a multiple of 4
        # See nrf_fstorage_write() in nrf_fstorage.c
        # TODO - Hack !!!!
        if inOffset >= 48:
           break
       
    outBuff += [SLIP_BYTE_END]

    return outBuff, inOffset



def BLE_DFU_checkRespForError(respLen, respMsg):
    rc = BLE_DFU_RC_RCVD_MSG_TOO_SHORT
    if respLen >= BLE_DFU_RESP_RESULT_CODE_FIELD_SZ:
       rc = respMsg[1]
       print("Result Code {}".format(rc))
       if rc != BLE_DFU_RES_CODE_SUCCESS:
          if rc == BLE_DFU_RES_CODE_EXT_ERROR:
             if respLen >= (BLE_DFU_RESP_RESULT_EXTENDED_CODE_FIELD_SZ + \
                            BLE_DFU_RESP_RESULT_CODE_FIELD_SZ):
                rc = BLE_DFU_RC_TGT_RESP_EXTENDED_ERROR_BASE + respMsg[2]
          else:
             rc = BLE_DFU_RC_TGT_RESP_ERROR_BASE + rc
    return rc



def ble_dfu_parse_resp(respMsg):
    retList = [BLE_DFU_RC_FAILURE, 0, 0, 0, 0]
    if args.debug:
       print("Parsing response msg of len ", len(respMsg))
    respLen = len(respMsg)
    if respLen > 0:
       origReqType = respMsg[0]
       if args.debug:
          print("Orig Request Type : 0x{:02x}".format(origReqType))

       respLen -= BLE_DFU_MSG_TYPE_FIELD_SZ

       rc = BLE_DFU_checkRespForError(respLen, respMsg)
       if rc != BLE_DFU_RES_CODE_SUCCESS:
          retList[0] = rc
          return retList

       if origReqType == BLE_DFU_OP_FIRMWARE_VERSION:
          print("Rcvd response to firmware version request")
          if respLen >= BLE_DFU_FW_VER_RESP_PYLD_SZ:
             rc = respMsg[1]
             print("Result Code 0x{:02x}".format(rc))
             if rc == BLE_DFU_RES_CODE_SUCCESS:
                retList[0] = BLE_DFU_RC_SUCCESS
                retList[1] = respMsg[2]
                retList[2] = __leTo32(respMsg[3:7])
                retList[3] = __leTo32(respMsg[7:11])
                retList[4] = __leTo32(respMsg[11:15])
             else:
                print("Response indicates error !! ")
                retList[0] = BLE_DFU_RC_TGT_RESP_ERROR_BASE + rc
          else:
             print("Response length < {}!!".format(BLE_DFU_FW_VER_RESP_PYLD_SZ))
             retList[0] = BLE_DFU_RC_RCVD_MSG_TOO_SHORT


       if origReqType == BLE_DFU_OP_OBJECT_EXECUTE:
          print("Rcvd response to OBJ EXEC Request")
          if respLen >= BLE_DFU_OBJ_EXEC_RESP_PYLD_SZ:
             rc = respMsg[1] 
             print("Result Code 0x{:02x}".format(rc))
             if rc == BLE_DFU_RES_CODE_SUCCESS:
                retList[0] = BLE_DFU_RC_SUCCESS
             else:
                print("Response indicates error !! ")
                retList[0] = BLE_DFU_RC_TGT_RESP_ERROR_BASE + rc
          else:
             print("Response length < {}!!".format(BLE_DFU_OBJ_EXEC_RESP_PYLD_SZ))
             retList[0] = BLE_DFU_RC_RCVD_MSG_TOO_SHORT


       if origReqType == BLE_DFU_OP_CRC_GET:
          print("Rcvd response to GET CRC request")
          if respLen >= BLE_DFU_GET_CRC_RESP_PYLD_SZ:
             rc = respMsg[1] 
             print("Result Code 0x{:02x}".format(rc))
             if rc == BLE_DFU_RES_CODE_SUCCESS:
                retList[0] = BLE_DFU_RC_SUCCESS
                retList[1] = __leTo32(respMsg[2:6])
                retList[2] = __leTo32(respMsg[6:10])
             else:
                print("Response indicates error !! ")
                retList[0] = BLE_DFU_RC_TGT_RESP_ERROR_BASE + rc
          else:
             print("Response length < {}!!".format(BLE_DFU_GET_CRC_RESP_PYLD_SZ))
             retList[0] = BLE_DFU_RC_RCVD_MSG_TOO_SHORT


       if origReqType == BLE_DFU_OP_OBJECT_CREATE:
          print("Rcvd response to OBJ CREATE request")
          if respLen >= BLE_DFU_OBJ_CREATE_RESP_PYLD_LEN_SZ:
             rc = respMsg[1] 
             print("Result Code 0x{:02x}".format(rc))
             if rc == BLE_DFU_RES_CODE_SUCCESS:
                retList[0] = BLE_DFU_RC_SUCCESS
             else:
                print("Response indicates error !! ")
                retList[0] = BLE_DFU_RC_TGT_RESP_ERROR_BASE + rc
          else:
             print("Response length < {}!!".format(BLE_DFU_OBJ_CREATE_RESP_PYLD_LEN_SZ))
             retList[0] = BLE_DFU_RC_RCVD_MSG_TOO_SHORT

           
       if origReqType == BLE_DFU_OP_OBJECT_SELECT:
          print("Rcvd response to OBJ SEL request")

          if respLen >= BLE_DFU_OBJ_SEL_RESP_PYLD_SZ:
             if rc == BLE_DFU_RES_CODE_SUCCESS:
                retList[1] = __leTo32(respMsg[2:6])
                retList[2] = __leTo32(respMsg[6:10])
                retList[3] = __leTo32(respMsg[10:14])
                retList[0] = BLE_DFU_RC_SUCCESS
             else:
                print("Response indicates error !! ")
                retList[0] = BLE_DFU_RC_TGT_RESP_ERROR_BASE + rc
          else:
             print("Response length < {}!!".format(BLE_DFU_OBJ_SEL_RESP_PYLD_SZ))
             retList[0] = BLE_DFU_RC_RCVD_MSG_TOO_SHORT

       if origReqType == BLE_DFU_OP_MTU_GET:
          print("Rcvd response to MTU GET request")
          if respLen >= BLE_DFU_GET_MTU_RESP_MSG_PYLD_SZ:
             rc = respMsg[1] 
             print("Result Code 0x{:02x}".format(rc))
             if rc == BLE_DFU_RES_CODE_SUCCESS:
                val16 = respMsg[3]
                val16 <<= 8
                val16 += respMsg[2]
                retList[0] = BLE_DFU_RC_SUCCESS
                retList[1] = val16
             else:
                print("Response indicates error !! ")
                retList[0] = BLE_DFU_RC_TGT_RESP_ERROR_BASE + rc
          else:       
             print("Response length < {}!!".format(BLE_DFU_GET_MTU_RESP_MSG_PYLD_SZ))
             retList[0] = BLE_DFU_RC_RCVD_MSG_TOO_SHORT
       
    else:
       print("Response too short !!")

    return retList



def ble_dfu_parse_tgt_msg(msg):
    retList = []
    msgType = msg[0]
    if args.debug:
       print("\nParsing rcvd msg .. type 0x{:02x}".format(msgType))
    if msgType == BLE_DFU_OP_RESPONSE:
       retList = ble_dfu_parse_resp(msg[1:])      
    else:
       print("Dropping msg !!")
    return retList



def ble_dfu_get_resp():
  retList = []
  while (1):
    msg = ble_dfu_get_tgt_msg()
    if len(msg) == 0:
       if args.debug:
          print("No msg from tgt... ")
       sleep(0.3)
    else:
       print("Rcvd msg of len {} from target ".format(len(msg)))
       if args.debug:
          __dump(msg)

       # Decode SLIP packet here !! TODO
       decMsgBuff = SLIP_decodeMsg(msg)
       if len(decMsgBuff) > 0:
          retList = ble_dfu_parse_tgt_msg(decMsgBuff)
       else:
          retList += [BLE_DFU_RC_SLIP_DECODE_FLR]
       break
  return retList



def ble_dfu_sendObjExecCmd():
    ble_dfu_send_msg(BLE_DFU_objExecCmdMsg)
    return ble_dfu_get_resp()



def ble_dfu_getMTU():
    ble_dfu_send_msg(BLE_DFU_getMTUMsg)
    return ble_dfu_get_resp()



def ble_dfu_getAppFwInfo():
    BLE_DFU_objSelMsg[2] = BLE_DFU_OBJ_TYPE_DATA
    ble_dfu_send_msg(BLE_DFU_objSelMsg)
    print("Sent Obj Select request to target ...")
    return ble_dfu_get_resp()



def ble_dfu_getInitPktInfo():
    BLE_DFU_objSelMsg[2] = BLE_DFU_OBJ_TYPE_COMMAND
    ble_dfu_send_msg(BLE_DFU_objSelMsg)
    print("Sent Obj Select request to target ...")
    return ble_dfu_get_resp()



def ble_dfu_sendAbortReqMsg():
    ble_dfu_send_msg(BLE_DFU_abortReqMsg)
    print("Sent DFU abort request to target ...")
    retList = ble_dfu_get_resp()
    rc = retList[0]
    if args.debug:
       print("ret code", rc)
    if rc != BLE_DFU_RC_SUCCESS:
       print("Abort request failed !!! ")
    else:
       print("DFU Aborted by target :-) ")
    return rc



def ble_dfu_sendFwVerReqMsg():
    ble_dfu_send_msg(BLE_DFU_fwVerReqMsg)
    print("Sent app fw version request to target ...")
    retList = ble_dfu_get_resp()
    rc = retList[0]
    if args.debug:
       print("ret code", rc)
    if rc != BLE_DFU_RC_SUCCESS:
       BLE_DFU_dispTgtErrorCode(rc)
    else:
       # print("sFVRM(): fw resp rcvd :-) ")
       print("[\n  Fw Type : {}".format(retList[1]))
       fwVerU32 = retList[2]
       v2 = int(fwVerU32/10000)
       v1 = int((fwVerU32 - (v2*10000)) / 100)
       v0 = fwVerU32 - (v2*10000) - (v1*100) 
       print("  Fw Version : {} -> {}.{}.{}".format(fwVerU32, v2, v1, v0))
       print("  Fw Start Addr : 0x{:08x}".format(retList[3]))
       print("  Fw Size : {} bytes\n]".format(retList[4]))
    return rc


def ble_dfu_sendExecObjMsg():
    ble_dfu_send_msg(BLE_DFU_execReqMsg)
    retList = ble_dfu_get_resp()
    rc = retList[0]
    if args.debug:
       print("ret code", rc)
    if rc != BLE_DFU_RC_SUCCESS:
       print("Object Exec request failed !!! ")
    else:
       print("Object Executed by Target :-) ")
    return rc



def ble_dfu_sendCreateObjMsg(objType, len):
    if args.debug:
       print("sCOM({}, {}) ....".format(objType, len))
    BLE_DFU_createObjReqMsg[2] = objType
    BLE_DFU_createObjReqMsg[3] = len & 0xff
    BLE_DFU_createObjReqMsg[4] = (len >> 8) & 0xff
    BLE_DFU_createObjReqMsg[5] = (len >> 16) & 0xff
    BLE_DFU_createObjReqMsg[6] = (len >> 24) & 0xff
    ble_dfu_send_msg(BLE_DFU_createObjReqMsg)
    retList = ble_dfu_get_resp()
    rc = retList[0]
    print("ret code", rc)
    if rc != BLE_DFU_RC_SUCCESS:
       BLE_DFU_dispTgtErrorCode(rc)
       print("Could not get object of type {} created on target !!! ".format(objType))
    else:
       print("Object of type {} created :-) ".format(objType))
    return rc



def ble_dfu_displayAppFwInfo():
    rc = True
    respList = ble_dfu_getAppFwInfo()
    rc = respList[0]
    if args.debug:
       print("ret code", rc)
    if rc != BLE_DFU_RC_SUCCESS:
       print("Could not get app fw offset and/or CRC32 from target... quitting !!! ")
       rc = False
    else:
       tgtMaxObjSz = respList[1]
       tgtAppFwOffset = respList[2]
       tgtAppFwCRC32 = respList[3]

       print("App FW info from target: max Sz {}, off {}, crc32 0x{:02x}".format(tgtMaxObjSz,
                                                                                 tgtAppFwOffset,
                                                                                 tgtAppFwCRC32))
    return rc



def ble_dfu_sendNextAppFwDataObject(imageBuff, imageOffset, maxDataObjSz):

    if args.debug:
       print("\n\n")
       print("sendNextAppFwDataObject({}, {}) Entry ..... ".format(imageOffset, maxDataObjSz))

    # TODO - Uncomment !!
    # if maxDataObjSz > 512:
    #    maxDataObjSz = 512

    # Calculate the CRC32 of the data object to be sent
    imageLen = len(imageBuff)

    if imageOffset % maxDataObjSz != 0:
       imageOffset = imageOffset - (imageOffset % maxDataObjSz)
       print("Re-Sending partially sent data object at offset {} ... ".format(imageOffset))

    lenLeftToSend = imageLen - imageOffset
    currDataObjSz = lenLeftToSend
    if currDataObjSz >= maxDataObjSz:
       currDataObjSz = maxDataObjSz
    rc = ble_dfu_sendCreateObjMsg(BLE_DFU_OBJ_TYPE_DATA, currDataObjSz)
    if rc != BLE_DFU_RC_SUCCESS:
       BLE_DFU_dispTgtErrorCode(rc)
       return rc, 0

    if args.debug:
       print("sleeping for 1 sec for erase to happen ....")
    sleep(1)

    if args.debug:
       print("Sending data obj of sz {} bytes at off {}".format(currDataObjSz,
                                                                imageOffset))
    chunkSize = BLE_DFU_MAX_SLIP_PDU_LEN
    chunkTxCnt = 0
    totBytesCons = 0

    currDataObjImageDataBuff = imageBuff[imageOffset : imageOffset + currDataObjSz]

    while 1:

       if totBytesCons >= currDataObjSz:
          break

       encTxBuff, bytesCons = SLIP_encodeChunk(BLE_DFU_OP_OBJECT_WRITE,
                                               currDataObjImageDataBuff[totBytesCons:],
                                               BLE_DFU_MAX_SLIP_PDU_LEN)
       chunkTxCnt += 1
       totBytesCons += bytesCons
       if args.debug:
          print("Data Obj Chunk # {}, Out Buff len {}, tot bytes consumed {}".format(chunkTxCnt, len(encTxBuff), totBytesCons))
       # __dump(encTxBuff)

       txMsgBuff = [len(encTxBuff)]
       txMsgBuff += encTxBuff

       ble_dfu_send_msg(txMsgBuff)
      
       if args.debug:
           print("Sent Image Chunk # {:02}, image off {}, tot data obj bytes cons {}".format(chunkTxCnt,
                                                                                             imageOffset + totBytesCons,
                                                                                             totBytesCons))
       else:
           print("Sent Image Chunk # {:02}, image off {:06}".format(chunkTxCnt, imageOffset + totBytesCons))

       if args.debug:
          print("sleeping for 0.1 sec .... ")
       sleep(0.1)
       if args.debug:
          print("--------------------------------------------------------------------------")

    print("All chunks in the current data obj sent ... ")

    # Get CRC32
    print("Getting CRC32 from target .... ")
    ble_dfu_send_msg(BLE_DFU_getCRCReqMsg)
    retList = ble_dfu_get_resp()
    rc = retList[0]
    if args.debug:
       print("Ret Code", rc)
    if rc != BLE_DFU_RC_SUCCESS:
       BLE_DFU_dispTgtErrorCode(rc)
       print("Could not get response to CRC command !!! ")
       return rc, 0

    tgtDataObjCRC32 = retList[2] 
    tgtDataObjOffset = retList[1]

    # The CRC32 is calculated over all the bytes received by the target

    print("Rcvd resp to calc crc cmd .... ")

    print("Offset rcvd {}, expected {}".format(tgtDataObjOffset,
                                               (imageOffset + currDataObjSz)))

    currDataObjCRC32 = __calcCRC32(bytes(imageBuff[0: tgtDataObjOffset]))
    print("CRC32 calcd over {} bytes is 0x{:08x}".format(tgtDataObjOffset, currDataObjCRC32))
    print("CRC32 rcvd 0x{:08x}, calcd 0x{:08x}".format(tgtDataObjCRC32, 
                                                       currDataObjCRC32))

    if tgtDataObjOffset != (imageOffset + currDataObjSz): 
       print("Target has not received the current data object fully !! ")
       return BLE_DFU_RC_DATA_OBJ_TRANSFER_ERROR, 0
    else:
       print("Target has received the sent data object fully :-) ")

    if tgtDataObjCRC32 != currDataObjCRC32:
       print("Curr data object CRC mismatch !!")
       return BLE_DFU_RC_DATA_OBJ_CRC32_MISMATCH, 0

    rc = ble_dfu_sendExecObjMsg()
    if rc != BLE_DFU_RC_SUCCESS:
       BLE_DFU_dispTgtErrorCode(rc)
       return rc, 0

    print("Data Object written to flash by target :- )")

    return BLE_DFU_RC_SUCCESS, currDataObjSz



def ble_dfu_sendAppFwToTgt(fwImageBuff):

    # A firmware image is split up into several data objects (of size maxDataObjSz)
    # that are transferred consecutively. If the transfer of a data object fails 
    # (for example, because of a power loss), the transfer can be continued instead 
    # of restarted. Therefore, the DFU controller starts by selecting the last data 
    # object that was sent and checks if it is complete and valid.

    # Max Data Object Size returned by the bootloader is 4096 bytes
    # So we will transfer 4096 bytes in N number of chunks. If the SLIP encoding does
    # not insert additional bytes, we are looking at chunks of 61 bytes (of raw image)
    # sent over the USB link to the STM32. This corresponds to 4096/61 = 68 chunks.
    # If SLIP encoding inserts extra bytes, this number (68) will go up.

    if args.debug:
       print("\n\n")
       print("SAFTT(): app fw sz {}".format(len(fwImageBuff)))
    rc = BLE_DFU_RC_SUCCESS

    dataObjTxCnt = 0

    while 1:
       respList = ble_dfu_getAppFwInfo()
       rc = respList[0]
       if args.debug:
          print("Ret Code", rc)
       if rc != BLE_DFU_RC_SUCCESS:
          BLE_DFU_dispTgtErrorCode(rc)
          print("Could not get app fw offset and/or CRC32 from target... quitting !!! ")
          break

       tgtAppMaxObjSz = respList[1]
       tgtAppFwOffset = respList[2]
       tgtAppFwCRC32 = respList[3]

       print("App FW info from target: max Sz {}, off {}, crc32 0x{:02x}".format(tgtAppMaxObjSz,
                                                                                 tgtAppFwOffset,
                                                                                 tgtAppFwCRC32))

       if tgtAppFwOffset == len(fwImageBuff):
          print("Full app firmware image transferred ... :-) ")
          rc = BLE_DFU_RC_SUCCESS
          break


       # if tgtAppFwOffset % tgtAppMaxObjSz != 0:
       #    print("App image offset {} invalid !!".format(tgtAppFwOffset))
       #    rc = BLE_DFU_RC_TGT_APP_FW_OFFSET_INVALID
       #    break

       rc, currObjBytesTxd = ble_dfu_sendNextAppFwDataObject(fwImageBuff, tgtAppFwOffset, tgtAppMaxObjSz)
       if rc != BLE_DFU_RC_SUCCESS:
          break

       if args.debug:
          print("Sent data object # {} of size {} at offset {} :-) ".format(dataObjTxCnt, currObjBytesTxd, tgtAppFwOffset))
          print("Next data Obj offset {}, file sz {}".format(tgtAppFwOffset + currObjBytesTxd, len(fwImageBuff)))

       if (tgtAppFwOffset + currObjBytesTxd) >= len(fwImageBuff):
           print("Full app firmware image transferred ... :-) ")
           rc = BLE_DFU_RC_SUCCESS
           break

       if args.debug:
          print("Sleep for 0.5 secs before sending next data obj ...")
       sleep(0.5)

       dataObjTxCnt += 1
       # if dataObjTxCnt >= 5:
       #    rc = BLE_DFU_RC_PARTIAL_SUCCESS 
       #    break

    return rc



def BLE_DFU_sendInitPktToTgt(initPktDataBuff, mtu):
    # The DFU controller sends a Create command to create a new data 
    # object and then transfers the init packet.

    initPktLen = len(initPktDataBuff)

    print("Sending Init pkt To Tgt: len is {} bytes, mtu is {} bytes".format(initPktLen, mtu))

    BLE_DFU_createObjReqMsg[2] = BLE_DFU_OBJ_TYPE_COMMAND
    BLE_DFU_createObjReqMsg[3] = initPktLen

    ble_dfu_send_msg(BLE_DFU_createObjReqMsg)
    retList = ble_dfu_get_resp()
    rc = retList[0]
    if args.debug:
       print("ret code", rc)
    if rc != BLE_DFU_RC_SUCCESS:
       print("Could not get object created on target !!! ")
       return rc

    if args.debug:
       print("Object created :-) ")

    # Now we send the init packet

    chunkSize = BLE_DFU_MAX_SLIP_PDU_LEN

    if args.debug:
       print("Sending init file in chunks of {} bytes ".format(chunkSize))

    chunkTxCnt = 0
    totBytesCons = 0
    while [ 1 ]:
       encTxBuff, bytesCons = SLIP_encodeChunk(BLE_DFU_OP_OBJECT_WRITE,
                                               BLE_DFU_initPacketData[totBytesCons:], 
                                               BLE_DFU_MAX_SLIP_PDU_LEN)
       chunkTxCnt += 1
       totBytesCons += bytesCons
       print("Init File Chunk # {}, Out Buff len {}, tot bytes consumed {}".format(chunkTxCnt, len(encTxBuff), totBytesCons))
       __dump(encTxBuff)

       txMsgBuff = [len(encTxBuff)]
       txMsgBuff += encTxBuff

       ble_dfu_send_msg(txMsgBuff)

       if totBytesCons >= initPktLen:
          break

       if args.debug:
          print("Sleeping for 0.1 secs .... ")
       sleep(0.1)

    print("Init file sent .... ")

    # Get CRC32
    print("Getting init file CRC32 from target .... ")
    ble_dfu_send_msg(BLE_DFU_getCRCReqMsg)
    retList = ble_dfu_get_resp()
    rc = retList[0]
    if args.debug:
       print("ret code", rc)
    if rc != BLE_DFU_RC_SUCCESS:
       print("Could not get response to CRC command !!! ")
       return rc

    tgtCRC32 = retList[2] 
    tgtOffset = retList[1]

    print("Rcvd response to calc CRC command ... crc32 0x{:08x}, offset {}".format(tgtCRC32, tgtOffset))

    if tgtOffset != initPktLen:
       print("Target has not received the full Init Packet !! ")
       return BLE_DFU_RC_INIT_PACKET_TRANSFER_ERROR

    localCRC32 = __calcCRC32(bytes(BLE_DFU_initPacketData))
    print("Calcd CRC32 0x{:08x}, Rcvd CRC32 0x{:08x}".format(localCRC32, tgtCRC32))

    if tgtCRC32 != localCRC32:
       print("Init File CRC mismatch !! ")
       return BLE_DFU_RC_INIT_FILE_CRC32_MISMATCH

    print("Target has received the init packet successfully !!")

    return BLE_DFU_RC_SUCCESS



def BLE_DFU_dispTgtErrorCode(errorCode):
   if errorCode >= BLE_DFU_RC_TGT_RESP_EXTENDED_ERROR_BASE: 
      errorCode -= BLE_DFU_RC_TGT_RESP_EXTENDED_ERROR_BASE
      errMsg = BLE_DFU_extErrCodeMap.get(errorCode)
      print("Target returned extended error :: [{}]".format(errMsg))
   else:
      if errorCode >= BLE_DFU_RC_TGT_RESP_ERROR_BASE: 
         errorCode -= BLE_DFU_RC_TGT_RESP_ERROR_BASE
         errMsg = BLE_DFU_errCodeMap.get(errorCode)
         if errMsg is not None:
            print("Target returned error :: [{}]".format(errMsg))



#--------------------------------------------------------------------------------
# Script starts here 
#-------------------------------------------------------------------------------

#SLIP_encBuff = [0x60, 0x03, 0x01, 0x00, 0xdb, 0xdc, 0x00, 0x00,
#                0x3c, 0x40, 0xa4, 0x53, 0xc0]
#__dump(SLIP_encBuff)
#SLIP_decodedBuff = SLIP_decodeMsg(SLIP_encBuff)
#__dump(SLIP_decodedBuff)
#quit()


################################################################################
# parse command-line arguments
################################################################################

parser = argparse.ArgumentParser()
parser.add_argument("--debug",        action="store_true", help="debug output")
parser.add_argument("--upg",          type=str, help="Upgrade to version. Example: --upg 4.3.1")
parser.add_argument("--ver",          action="store_true", help="Show current app fw version")
parser.add_argument("--abort",        action="store_true", help="Abort DFU process")
parser.add_argument("--status",       action="store_true", help="Get status from the target")
args = parser.parse_args()

# print("args : ", sys.argv)

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)
if not dev:
   print("No spectrometer found")
   sys.exit()

if args.abort:
   ble_dfu_sendAbortReqMsg()
   quit()

if args.ver:
   ble_dfu_sendFwVerReqMsg()
   quit()

if args.status:
   respList = ble_dfu_getInitPktInfo()
   rc = respList[0]
   if rc != BLE_DFU_RC_SUCCESS:
      BLE_DFU_dispTgtErrorCode(rc)
      print("Could not get init packet offset and/or CRC32 from target ... !!! \n")
   else:
      maxSz = respList[1]
      offset = respList[2]
      crc32 = respList[3]

      print("Init pkt info from target: [max Sz {}, off {}, crc32 0x{:02x}]".format(maxSz, 
                                                                                  offset,
                                                                                  crc32))
      print("")

   respList = ble_dfu_getAppFwInfo()
   rc = respList[0]
   if rc != BLE_DFU_RC_SUCCESS:
      BLE_DFU_dispTgtErrorCode(rc)
      print("Could not get app fw offset and/or CRC32 from target ... !!!  \n")
      rc = False
   else:
      maxSz = respList[1]
      offset = respList[2]
      crc32 = respList[3]

      print("App fw info from target: [max Sz {}, off {}, crc32 0x{:02x}]".format(maxSz, 
                                                                                offset,
                                                                                crc32))
   quit()

if args.upg is not None:
    print("Upgrading to version {}".format(args.upg))
    # Read in the init file
    BLE_DFU_initFileName = "170086_sig_ble_nrf_v" + args.upg + ".dat"
    print("Reading in init data file {}".format(BLE_DFU_initFileName))
    try:
       with open(BLE_DFU_initFileName, mode='rb') as BLE_DFU_initFileObj: # b is important -> binary
            BLE_DFU_initPacketData = list(BLE_DFU_initFileObj.read())
            # __dump(BLE_DFU_initPacketData)
    except:
       print("Could not open init data file !!")
       quit()                                                

    print("Read init packet data of len {} bytes".format(len(BLE_DFU_initPacketData)))

    # Read in the application firmware image file
    BLE_DFU_appFwFileName = "170086_sig_ble_nrf_v" +  args.upg + ".bin"
    print("Reading in app fw image file {}".format(BLE_DFU_appFwFileName))
    try:
       with open(BLE_DFU_appFwFileName, mode='rb') as BLE_DFU_appFwFileObj: # b is important -> binary
            BLE_DFU_appFwImage = list(BLE_DFU_appFwFileObj.read())
            # __dump(BLE_DFU_appFwImage)
    except:
       print("Could not open app fw image file !!")
       quit()                                                

    print("Read app fw image of len {} bytes".format(len(BLE_DFU_appFwImage)))
else:
    print("Please specify app fw version to upgrade to !!")
    quit()


#crcDataObj0 = __calcCRC32(bytes(BLE_DFU_appFwImage))
#crcDataObj1 = __calcCRC32(bytes(BLE_DFU_appFwImage[4096: 8192]))
#crcDataObj2 = __calcCRC32(bytes(BLE_DFU_appFwImage[0: 8192]))
#print("crc 0x{:08x}".format(crcDataObj0))
#print(" crc 0x{:08x} 0x{:08x} 0x{:08x}", crcDataObj0, crcDataObj1, crcDataObj2)
#quit()

print('-------------------------------------------------------')
respList = ble_dfu_getMTU()
rc = respList[0]
print("ret code", rc)
if rc != BLE_DFU_RC_SUCCESS:
   BLE_DFU_dispTgtErrorCode(rc)
   print("Could not get MTU from target... quitting !!! ")
   quit()
tgtMTU = respList[1]
print("MTU rcvd from tgt is ", tgtMTU)


print('-------------------------------------------------------')
respList = ble_dfu_getInitPktInfo()
rc = respList[0]
print("ret code", rc)
if rc != BLE_DFU_RC_SUCCESS:
   BLE_DFU_dispTgtErrorCode(rc)
   print("Could not get init packet offset and/or CRC32 from target... quitting !!! ")
   quit()

tgtInitPktMaxSz = respList[1]
tgtInitPktOffset = respList[2]
tgtInitPktCRC32 = respList[3]

print("Init pkt info from target: max Sz {}, off {}, crc32 0x{:02x}".format(tgtInitPktMaxSz, 
                                                                            tgtInitPktOffset,
                                                                            tgtInitPktCRC32))

#quit()

initFileCalcdCRC32 = __calcCRC32(bytes(BLE_DFU_initPacketData))

print("init packet calcd CRC32 is 0x{:08x}, size is {}".format(initFileCalcdCRC32, \
                                                               len(BLE_DFU_initPacketData)))


# If there is no init packet or the init packet is invalid, create a new object
if (tgtInitPktOffset != len(BLE_DFU_initPacketData) \
    or (tgtInitPktCRC32 != initFileCalcdCRC32)):
   rc = BLE_DFU_sendInitPktToTgt(BLE_DFU_initPacketData, tgtMTU) 
   if rc != BLE_DFU_RC_SUCCESS:
      BLE_DFU_dispTgtErrorCode(rc)
      quit()
else:
   print("Target has received valid init packet .... ")

# When the init packet is available on the target, the DFU controller issues 
# an Execute command to initiate the validation of the init packet.

respList = ble_dfu_sendObjExecCmd()
rc = respList[0]
print("ret code", rc)
if rc != BLE_DFU_RC_SUCCESS:
   BLE_DFU_dispTgtErrorCode(rc)
   print("Obj Exec did not succeed ... quitting !!! ")
   quit()

print("Target has successfully validated the init packet .... :-)  ")

# Get info from the target on the application fw image

print('Now sending App Firmware Image .....')

rc = ble_dfu_sendAppFwToTgt(BLE_DFU_appFwImage)
if rc == BLE_DFU_RC_PARTIAL_SUCCESS: 
   print("Not resetting UART back to normal mode ...")
   print("Done ....")
   quit()

try:
  result = dev.ctrl_transfer(HOST_TO_DEVICE,
                             0xff,
                             0x32,
                             0,
                             64)
except Exception as exc:
  print("Failed to send UART reset command to SiG !!!")

print("Sent UART reset command to SiG ....")
print("Done ....")

