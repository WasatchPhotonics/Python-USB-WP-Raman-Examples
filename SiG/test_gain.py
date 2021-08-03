#!/usr/bin/env python

import os
import sys
import usb.core
import platform
from time import sleep

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUFFER_SIZE     = 8
BUF             = [0] * BUFFER_SIZE
TIMEOUT_MS      = 1000

class TestFixture:

    def __init__(self):

        print("searching for spectrometer with VID 0x%04x, PID 0x%04x" % (VID, PID))
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        if dev is None:
            print("No matching spectrometer found")
            sys.exit(1)
        #print(dev)

        if os.name == "posix":
            dev.set_configuration()
            usb.util.claim_interface(dev, 0)

        self.dev = dev

    def run(self):
        dB = 0
        while dB < 2.1:
            print("\nrun: dB = %.1f" % dB)
            self.set_detector_gain(dB)
            self.get_detector_gain()
            sleep(1)
            dB += 0.1

    def float_to_uint16(self, gain):
        msb = int(round(gain, 5)) & 0xff
        lsb = round((gain - msb) * 256) & 0xff
        raw = (msb << 8) | lsb
        print("float_to_uint16: gain %f -> msb %d, lsb %d -> raw 0x%04x" % (gain, msb, lsb, raw))
        return raw

    def set_detector_gain(self, gain):
        raw = self.float_to_uint16(gain)
        return self.send_code(0xb7, raw, label="SET_DETECTOR_GAIN")

    def get_detector_gain(self):
        result = self.get_code(0xc5, label="GET_DETECTOR_GAIN")
        if result is None:
            print("GET_DETECTOR_GAIN returned NULL!")
            return -1

        lsb = result[0] # LSB-MSB
        msb = result[1]
        raw = (msb << 8) | lsb

        gain = msb + lsb / 256.0
        print("get_detector_gain: %f (raw 0x%04x, msb %d, lsb %d)" % (gain, raw, msb, lsb))

        return gain

    def send_code(self, bRequest, wValue=0, wIndex=0, data_or_wLength=None, label=""):
        prefix = "" if not label else ("%s: " % label)
        result = None
        data_or_wLength = [0] * 8

        try:
            result = self.dev.ctrl_transfer(HOST_TO_DEVICE,
                                            bRequest,
                                            wValue,
                                            wIndex,
                                            data_or_wLength) 
        except Exception as exc:
            print("Hardware Failure FID Send Code Problem with ctrl transfer")
            return None

        print("%ssend_code: request 0x%02x value 0x%04x index 0x%04x data/len %s: result %s" % (
            prefix, bRequest, wValue, wIndex, data_or_wLength, result))
        return result

    def get_code(self, bRequest, wValue=0, wIndex=0, wLength=64, label="", msb_len=None, lsb_len=None):
        prefix = "" if not label else ("%s: " % label)
        result = None

        try:
            result = self.dev.ctrl_transfer(DEVICE_TO_HOST,
                                            bRequest,
                                            wValue,
                                            wIndex,
                                            wLength)
        except Exception as exc:
            print("Hardware Failure FID Get Code Problem with ctrl transfer")
            return None

        print("%sget_code: request 0x%02x value 0x%04x index 0x%04x = [%s]" % (
            prefix, bRequest, wValue, wIndex, result))

        if result is None:
            print("get_code[%s]: received null" % label)
            return None

        # demarshall or return raw array
        value = 0
        if msb_len is not None:
            for i in range(msb_len):
                value = value << 8 | result[i]
            return value
        elif lsb_len is not None:
            for i in range(lsb_len):
                value = (result[i] << (8 * i)) | value
            return value
        else:
            return result

################################################################################
# main()
################################################################################

fixture = TestFixture()
fixture.run()
