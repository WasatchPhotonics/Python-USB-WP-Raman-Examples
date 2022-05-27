import usb.core
import time
import sys

HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xc0
TIMEOUT_MS      = 1000

LASER_CAN_FIRE  = 0xef
LASER_IS_FIRING = 0x0d # second-tier

def getRaw(bRequest, wValue=0, wIndex=0, length=64):
    return dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, length, TIMEOUT_MS)

def getValue(bRequest, wValue=0, wIndex=0, length=1):
    data = getRaw(bRequest, wValue, wIndex, length)
    datalen = len(data)

    result = 0
    for i in range(datalen):
        result = (result << 8) | data[datalen - i - 1]
    return result 

def setValue(cmd, wValue, wIndex=0):
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, wValue, wIndex, None, TIMEOUT_MS) 

def setLaserEnable(flag):
    setValue(0xbe, 1 if flag else 0)

def showStatus(cnt=1):
    for i in range(cnt):
        can_fire_result  = getValue(bRequest=LASER_CAN_FIRE)
        is_firing_result = getValue(bRequest=0xff, wValue=LASER_IS_FIRING)
        print(f"Status %02d/%02d: laser_can_fire (0x%02x) %d, laser_is_firing (0x%02x) %d" % (
            i + 1,          cnt,
            LASER_CAN_FIRE, can_fire_result,
            LASER_IS_FIRING, is_firing_result))
        time.sleep(0.5)

################################################################################
# main()
################################################################################

dev = usb.core.find(idVendor=0x24aa, idProduct=0x2000)
if dev is None:
    print("No spectrometers found")
    sys.exit(0)

# show firmware versions
print("FX2 FW Version %s" % ".".join(str(x) for x in list(reversed(list(getRaw(0xc0, length=4))))))
print("FPGA FW Version %s" % "".join(chr(c) for c in getRaw(0xb4, length=7)))

# show interlock status before laser enabled
showStatus()

# fire laser, displaying status during warm-up
print("Press <return> to fire laser...", end='')
input()
setLaserEnable(True)

# show interlock while laser comes up
showStatus(20)

# disable laser
print("Press <return> to disablelaser...", end='')
input()
setLaserEnable(False)

# show interlock after laser off
showStatus()
