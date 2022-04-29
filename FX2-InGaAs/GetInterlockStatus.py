import usb.core
import time

HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xc0
TIMEOUT_MS      = 1000

# used to get microcontroller and FPGA firmware versions
def Get_Raw(bRequest, ByteCount=64, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, 0, 0, ByteCount, TIMEOUT_MS)

# used to read interlock status
def getValue(bRequest, wValue=0, wIndex=0, len_lsb=1):
    data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, len_lsb, TIMEOUT_MS)
    datalen = len(data)

    # convert response array to uint in LSB order
    result = 0
    for i in range(datalen):
        result = (result << 8) | data[datalen - i - 1]
    return result 

# used to dis/enable laser
def setValue(cmd, wValue, wIndex=0):
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, wValue, wIndex, None, TIMEOUT_MS) 

def setLaserEnable(flag):
    setValue(0xbe, 1 if flag else 0)

def showStatus(cnt=1):
    for i in range(cnt):
        laser_can_fire = getValue(bRequest=0xef)
        laser_is_firing = getValue(bRequest=0xff, wValue=0x0d)
        print(f"Status {i}/{cnt}: laser_can_fire {laser_can_fire}, laser_is_firing {laser_is_firing}")
        time.sleep(0.5)

################################################################################
# main()
################################################################################

dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)

# show firmware versions
print("uC FW Version %s" % ".".join(str(x) for x in list(reversed(list(Get_Raw(0xc0, 4))))))
print("FPGA FW Version %s" % "".join(chr(c) for c in Get_Raw(0xb4, 7)))

# show interlock before laser
showStatus()

# fire laser
print("Press <return> to fire laser...", end='')
x = input()
setLaserEnable(True)

# show interlock while laser comes up
showStatus(20)

# disable laser
print("Press <return> to disablelaser...", end='')
x = input()
setLaserEnable(False)

# show interlock after laser off
showStatus()
