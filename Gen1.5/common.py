# This file is not intended to be executed separately.  It is imported by other
# scripts in this directory.

import sys

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS     = 1000

def send_cmd_uint40(dev, bRequest, uint40):
    buf = [0] * 8
    lsw    = (uint40      ) & 0xffff # bits 0-15
    msw    = (uint40 >> 16) & 0xffff # bits 16-31
    buf[0] = (uint40 >> 32) & 0xff   # bits 32-39
    send_cmd(dev, bRequest, wValue=lsw, wIndex=msw, buf=buf)

def send_cmd(dev, bRequest, wValue=0, wIndex=0, buf=None):
    if buf is None and dev.idProduct == 0x4000:
        buf = [0] * 8
    print(">> sending bRequest 0x%02x, wValue 0x%04x, wIndex 0x%04x, buf %s" % (bRequest, wValue, wIndex, buf))
    dev.ctrl_transfer(HOST_TO_DEVICE, bRequest, wValue, wIndex, buf, TIMEOUT_MS)

def get_cmd(dev, bRequest, wValue=0, wIndex=0, wLength=64, msb_len=None, lsb_len=None):
    print("<< reading bRequest 0x%02x, wValue 0x%04x, wIndex 0x%04x" % (bRequest, wValue, wIndex))
    result = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, wLength)
    print("<< [%s]" % result)
    if result is None:
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

##
# Uses the "getter" opcode in bRequest to determine that the specified big- or 
# little-endian value (per msb_len or lsb_len) matches "expected".
def verify_state(dev, bRequest, wValue=0, wIndex=0, wLength=64, msb_len=None, lsb_len=None, expected=0, label="unknown"):
    print("Verifying %s state is %d" % (label, expected))
    if msb_len is not None:
        state = get_cmd(dev, bRequest, msb_len=msb_len)
    else:
        state = get_cmd(dev, bRequest, lsb_len=lsb_len)

    if state == expected:
        print("Verified %s state (matched expected %d)" % (label, expected))
    else:
        print("ERROR: unexpected %s state: %d (raw 0x%010x) (expected %d)" % (label, state, state, expected))
        sys.exit(1)
