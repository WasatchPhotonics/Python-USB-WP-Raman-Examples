from ctypes import *

# see page 330 of Andor SDK documentation
SUCCESS = 20002

# not sure where this comes from...ask Caleb - TS
SHUTTER_SPEED_MS = 35

INTEGRATION_TIME_MS = 10

# note: need to change this to "64" under 64bit Python
driver = cdll.atmcd32d

# default to first Andor camera found on the USB bus
specIndex = 0 

################################################################################
# open camera connection
################################################################################

cameraHandle = c_int()
assert(SUCCESS == driver.GetCameraHandle(specIndex, byref(cameraHandle))), "unable to get camera handle"
assert(SUCCESS == driver.SetCurrentCamera(cameraHandle.value)), "unable to set current camera"

print("initializing camera...", end='')
init_str = create_string_buffer(b'\000' * 16)
assert(SUCCESS == driver.Initialize(init_str)), "unable to initialize camera"
print("success")

################################################################################
# serial number
################################################################################

sn = c_int()
assert(SUCCESS == cdll.atmcd32d.GetCameraSerialNumber(byref(sn))), "can't get serial number"
print(f"connected to Andor CCD-{sn.value}")

################################################################################
# TEC setpoint
################################################################################

minTemp = c_int()
maxTemp = c_int()
assert(SUCCESS == driver.GetTemperatureRange(byref(minTemp), byref(maxTemp))), "unable to read temperature range"
setpointDegC = int(round((minTemp.value + maxTemp.value) / 2.0))
assert(SUCCESS == driver.SetTemperature(setpointDegC)), "unable to set temperature midpoint"
print(f"set TEC to {setpointDegC} C (range {minTemp.value}, {maxTemp.value})")

################################################################################
# detector area
################################################################################

xPixels = c_int()
yPixels = c_int()
assert(SUCCESS == driver.GetDetector(byref(xPixels), byref(yPixels))), "unable to read detector dimensions"
print(f"detector {xPixels.value} width x {yPixels.value} height")
pixels = xPixels.value

################################################################################
# set basic acquisition parameters
################################################################################

assert(SUCCESS == driver.CoolerON()), "unable to enable TEC"
print("enabled TEC")

assert(SUCCESS == driver.SetAcquisitionMode(1)), "unable to set acquisition mode"
print("configured acquisition mode (single scan)")

assert(SUCCESS == driver.SetTriggerMode(0)), "unable to set trigger mode"
print("set trigger mode")

assert(SUCCESS == driver.SetReadMode(0)), "unable to set read mode"
print("set read mode (full vertical binning)")

################################################################################
# Set vertical and horizontal speed
################################################################################

# vertical speed (set to recommended)
VSnumber = c_int()
speed = c_float()
assert(SUCCESS == driver.GetFastestRecommendedVSSpeed(byref(VSnumber), byref(speed))), "unable to get fastest recommended VS speed"
assert(SUCCESS == driver.SetVSSpeed(VSnumber.value)), f"unable to set VS speed {VSnumber.value}"
print(f"set vertical speed to {VSnumber.value}")

# horizontal speed (set to max)
nAD = c_int()
sIndex = c_int()
STemp = 0.0
HSnumber = 0
ADnumber = 0
assert(SUCCESS == driver.GetNumberADChannels(byref(nAD))), "unable to get number of AD channels"
for iAD in range(nAD.value):
    assert(SUCCESS == driver.GetNumberHSSpeeds(iAD, 0, byref(sIndex))), f"unable to get number of HS speeds for AD {iAD}"
    for iSpeed in range(sIndex.value):
        assert(SUCCESS == driver.GetHSSpeed(iAD, 0, iSpeed, byref(speed))), f"unable to get HS speed for iAD {iAD}, iSpeed {iSpeed}"
        if speed.value > STemp:
            STemp = speed.value
            HSnumber = iSpeed
            ADnumber = iAD
assert(SUCCESS == driver.SetADChannel(ADnumber)), "unable to set AD channel to {ADnumber}"
assert(SUCCESS == driver.SetHSSpeed(0, HSnumber)), "unable to set HS speed to {HSnumber}"
print(f"set AD channel {ADnumber} with horizontal speed {HSnumber} ({STemp})")

################################################################################
# shutter
################################################################################

# configure internal/external shutter
print("Setting shutter to fully automatic external with internal always open")
assert(SUCCESS == driver.SetShutterEx(1, 1, SHUTTER_SPEED_MS, SHUTTER_SPEED_MS, 0)), "unable to set external shutter params"

################################################################################
# integration time
################################################################################

print(f"setting integration time to {INTEGRATION_TIME_MS}ms")
exposure = c_float()
accumulate = c_float()
kinetic = c_float()
assert(SUCCESS == driver.SetExposureTime(c_float(INTEGRATION_TIME_MS / 1000.0))), "unable to set integration time"
assert(SUCCESS == driver.GetAcquisitionTimings(byref(exposure), byref(accumulate), byref(kinetic))), "unable to read acquisition timings"
print(f"read integration time of {exposure.value:.3f}sec (expected {INTEGRATION_TIME_MS}ms)")
