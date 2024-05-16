#!/usr/bin/env python

import sys
import zlib
import argparse


APP_FW_START_ADDRESS_IN_FLASH = 0x26000

DFU_SETTINGS_CRC_FIELD_OFF = 0x0
DFU_SETTINGS_VERSION_FIELD_OFF = 0x4
DFU_SETTINGS_PROGRESS_UPD_START_ADDR_FIELD_OFF  = 0x48
DFU_SETTINGS_INIT_COMMAND_FIELD_OFF  = 0x5c
DFU_SETTINGS_BOOT_VALIDATION_CRC_FIELD_OFF  = 0x25c
DFU_SETTINGS_BOOT_VAL_SOFTDEVICE_TYPE_FIELD_OFF  = 0x260
DFU_SETTINGS_BOOT_VAL_SOFTDEVICE_BYTES_FIELD_OFF  = 0x261
DFU_SETTINGS_BOOT_VAL_APP_TYPE_FIELD_OFF = 0x2a1
DFU_SETTINGS_BOOT_VAL_APP_BYTES_FIELD_OFF  = 0x2a2
DFU_SETTINGS_BOOT_VAL_BOOTLOADER_TYPE_FIELD_OFF  = 0x2e2
DFU_SETTINGS_BOOT_VAL_BOOTLOADER_BYTES_FIELD_OFF  = 0x2a3
DFU_SETTINGS_PEER_DATA_FIELD_OFF  = 0x323
DFU_SETTINGS_ADV_NAME_FIELD_OFF  = 0x363

DFU_SETTINGS_VERSION = 2
DFU_SETTINGS_BUFF_SIZE_BYTES = 896

DFU_settingsBuff = [0] * DFU_SETTINGS_BUFF_SIZE_BYTES

NRF_DFU_BANK_INVALID       =  0x00  # < Invalid image.
NRF_DFU_BANK_VALID_APP     =  0x01  # < Valid application.
NRF_DFU_BANK_VALID_SD      =  0xA5  # < Valid SoftDevice.
NRF_DFU_BANK_VALID_BL      =  0xAA  # < Valid bootloader.
NRF_DFU_BANK_VALID_SD_BL   =  0xAC  # < Valid SoftDevice and bootloader.
NRF_DFU_BANK_VALID_EXT_APP =  0xB1  # < Valid application designated for a remote node.

NRF_DFU_BOOT_VALIDATION_TYPE_NONE = 0
NRF_DFU_BOOT_VALIDATION_TYPE_CRC  = 1
NRF_DFU_BOOT_VALIDATION_TYPE_SHA256 = 2
NRF_DFU_BOOT_VALIDATION_TYPE_ECDSA_P256_SHA256 = 3


def __dump(buff):
    print("------------------------------------------------------------------")
    print("Dumping buffer of len", len(buff))
    print("------------------------------------------------------------------")
    str = ""
    cnt = 0
    totCnt = 0
    for byte in buff:
        if cnt == 0:
            str += f"[{totCnt:#0{5}x}]" + "  "
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

def __calcCRC32(inBuff):
    crc32 = zlib.crc32(inBuff)
    # print("Calc CRC32 is 0x{:08x}".format(crc32))
    return crc32

def __hostToLE32(val32):
    buff = [0, 0, 0, 0]
    buff[0] = val32 & 0xff
    buff[1] = (val32 >> 8) & 0xff
    buff[2] = (val32 >> 16) & 0xff
    buff[3] = (val32 >> 24) & 0xff
    return buff

parser = argparse.ArgumentParser()
parser.add_argument("--ver", type=str, help="Upgrade to version. Example: --ver 4.3.1")
args = parser.parse_args()

offset = 0

crc32 = 0
DFU_settingsBuff[offset:offset + 4] = __hostToLE32(crc32)
offset += 4

# settings version
DFU_settingsBuff[offset:offset + 4] = __hostToLE32(DFU_SETTINGS_VERSION)
offset += 4


if args.ver is not None:

    ver_numbers = args.ver.split('.')
    # print(ver_numbers)

    if len(ver_numbers) != 3:
       print("Enter valid version number. Example: 4.3.1 !!")
       quit()

    n1 = int(ver_numbers[0])
    n2 = int(ver_numbers[1])
    n3 = int(ver_numbers[2])

    if n1 < 0 or n1 > 99 \
       or n2 < 0 or n2 > 99 \
       or n3 < 0 or n3 > 99:
       print("Enter valid version number. Example: 4.3.1 !!")
       quit()
       
    app_ver_num_int = n1*10000 + n2*100 + n3
    print("version number 0x{:x}".format(app_ver_num_int))

    # app fw version
    DFU_settingsBuff[offset:offset + 4] = __hostToLE32(app_ver_num_int)
    offset += 4


    # Read in the application firmware image file
    BLE_DFU_appFwFileName = "170086_sig_ble_nrf_v" +  args.ver + ".bin"
    print("Reading in app fw image file {}".format(BLE_DFU_appFwFileName))
    try:
       with open(BLE_DFU_appFwFileName, mode='rb') as BLE_DFU_appFwFileObj: # b is important -> binary
            BLE_DFU_appFwImage = list(BLE_DFU_appFwFileObj.read())
            # __dump(BLE_DFU_appFwImage)
    except:
       print("Could not open app fw image file !!")
       quit()

    print("App Fw Image Size {} bytes".format(len(BLE_DFU_appFwImage)))

    offset += (4 + 4 + 4)
    DFU_settingsBuff[offset:offset + 4] = __hostToLE32(len(BLE_DFU_appFwImage))
    offset += 4
    appFwImageCRC32 = __calcCRC32(bytes(BLE_DFU_appFwImage))
    print("App Fw Image CRC32 0x{:x} ".format(appFwImageCRC32))
    DFU_settingsBuff[offset:offset + 4] = __hostToLE32(appFwImageCRC32)
    offset += 4
    DFU_settingsBuff[offset:offset + 4] = __hostToLE32(NRF_DFU_BANK_VALID_APP)

 
    offset = DFU_SETTINGS_PROGRESS_UPD_START_ADDR_FIELD_OFF
    DFU_settingsBuff[offset:offset + 4] = __hostToLE32(APP_FW_START_ADDRESS_IN_FLASH)

    offset = DFU_SETTINGS_BOOT_VAL_APP_TYPE_FIELD_OFF
    DFU_settingsBuff[offset] = NRF_DFU_BOOT_VALIDATION_TYPE_CRC
    offset += 1
    DFU_settingsBuff[offset:offset + 4] = __hostToLE32(appFwImageCRC32)
    
    bootValCRC32 = __calcCRC32(bytes(DFU_settingsBuff[DFU_SETTINGS_BOOT_VAL_SOFTDEVICE_TYPE_FIELD_OFF: \
                                                      DFU_SETTINGS_PEER_DATA_FIELD_OFF]))
    print("Boot Validation CRC32 0x{:x} ".format(bootValCRC32))
    offset = DFU_SETTINGS_BOOT_VALIDATION_CRC_FIELD_OFF 
    DFU_settingsBuff[offset:offset + 4] = __hostToLE32(bootValCRC32)

    # Overall CRC is calculated from the s_dfu_settings struct, except the crc itself, 
    # the init command, bond data, and boot validation.

    DFU_settingsCRC32 =  __calcCRC32(bytes(DFU_settingsBuff[DFU_SETTINGS_VERSION_FIELD_OFF: \
                                                            DFU_SETTINGS_INIT_COMMAND_FIELD_OFF]))
    print("DFU Settings CRC32 0x{:x} ".format(DFU_settingsCRC32))
    offset = DFU_SETTINGS_CRC_FIELD_OFF
    DFU_settingsBuff[offset:offset + 4] = __hostToLE32(DFU_settingsCRC32)

    __dump(DFU_settingsBuff)
    outputFileName = "dfu_settings_" + args.ver + ".bin"
    try:
       with open(outputFileName, mode='wb') as settingsFileObj: # b is important -> binary
           settingsFileObj.write(bytes(DFU_settingsBuff))
           settingsFileObj.close()
           print("written DFU settings to binary file {}".format(outputFileName))
    except:
       print("Could not open bin data file to write to !!")
       quit()                                                

else:
    print("Please specify app fw version number (example: 4.3.1) !!")
