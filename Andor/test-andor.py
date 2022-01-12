import struct
from ctypes import *

class Fixture:

    SUCCESS = 20002             #!< see page 330 of Andor SDK documentation
    SHUTTER_SPEED_MS = 35       #!< not sure where this comes from...ask Caleb - TS

    def __init__(self):
        self.spec_index = 0 

        # select appropriate Andor library per architecture
        if 64 == struct.calcsize("P") * 8:
            self.driver = cdll.atmcd64d
        else:
            self.driver = cdll.atmcd32d

        self.open()

    def open(self):
        cameraHandle = c_int()
        assert(self.SUCCESS == self.driver.GetCameraHandle(self.spec_index, byref(cameraHandle))), "unable to get camera handle"
        assert(self.SUCCESS == self.driver.SetCurrentCamera(cameraHandle.value)), "unable to set current camera"
        print("initializing camera...", end='')

        # not sure init_str is actually required
        init_str = create_string_buffer(b'\000' * 16)
        assert(self.SUCCESS == self.driver.Initialize(init_str)), "unable to initialize camera"
        print("self.SUCCESS")

        self.get_serial_number()
        self.init_tec_setpoint()
        self.init_detector_area()

        assert(self.SUCCESS == self.driver.CoolerON()), "unable to enable TEC"
        print("enabled TEC")

        assert(self.SUCCESS == self.driver.SetAcquisitionMode(1)), "unable to set acquisition mode"
        print("configured acquisition mode (single scan)")

        assert(self.SUCCESS == self.driver.SetTriggerMode(0)), "unable to set trigger mode"
        print("set trigger mode")

        assert(self.SUCCESS == self.driver.SetReadMode(0)), "unable to set read mode"
        print("set read mode (full vertical binning)")

        self.init_detector_speed()

        assert(self.SUCCESS == self.driver.SetShutterEx(1, 1, self.SHUTTER_SPEED_MS, self.SHUTTER_SPEED_MS, 0)), "unable to set external shutter"
        print("set shutter to fully automatic external with internal always open")

        self.set_integration_time_ms(10)

    def get_serial_number(self):
        sn = c_int()
        assert(self.SUCCESS == cdll.atmcd32d.GetCameraSerialNumber(byref(sn))), "can't get serial number"
        self.serial = "CCD-{sn.value}"
        print(f"connected to {self.serial}")

    def init_tec_setpoint(self):
        minTemp = c_int()
        maxTemp = c_int()
        assert(self.SUCCESS == self.driver.GetTemperatureRange(byref(minTemp), byref(maxTemp))), "unable to read temperature range"
        self.detector_temp_min = minTemp.value
        self.detector_temp_max = maxTemp.value

        self.setpoint_deg_c = int(round((self.detector_temp_min + self.detector_temp_max) / 2.0))
        assert(self.SUCCESS == self.driver.SetTemperature(self.setpoint_deg_c)), "unable to set temperature midpoint"
        print(f"set TEC to {self.setpoint_deg_c} C (range {self.detector_temp_min}, {self.detector_temp_max})")

    def init_detector_area(self):
        xPixels = c_int()
        yPixels = c_int()
        assert(self.SUCCESS == self.driver.GetDetector(byref(xPixels), byref(yPixels))), "unable to read detector dimensions"
        print(f"detector {xPixels.value} width x {yPixels.value} height")
        pixels = xPixels.value

    def init_detector_speed (self):
        # set vertical to recommended
        VSnumber = c_int()
        speed = c_float()
        assert(self.SUCCESS == self.driver.GetFastestRecommendedVSSpeed(byref(VSnumber), byref(speed))), "unable to get fastest recommended VS speed"
        assert(self.SUCCESS == self.driver.SetVSSpeed(VSnumber.value)), f"unable to set VS speed {VSnumber.value}"
        print(f"set vertical speed to {VSnumber.value}")

        # set horizontal to max
        nAD = c_int()
        sIndex = c_int()
        STemp = 0.0
        HSnumber = 0
        ADnumber = 0
        assert(self.SUCCESS == self.driver.GetNumberADChannels(byref(nAD))), "unable to get number of AD channels"
        for iAD in range(nAD.value):
            assert(self.SUCCESS == self.driver.GetNumberHSSpeeds(iAD, 0, byref(sIndex))), f"unable to get number of HS speeds for AD {iAD}"
            for iSpeed in range(sIndex.value):
                assert(self.SUCCESS == self.driver.GetHSSpeed(iAD, 0, iSpeed, byref(speed))), f"unable to get HS speed for iAD {iAD}, iSpeed {iSpeed}"
                if speed.value > STemp:
                    STemp = speed.value
                    HSnumber = iSpeed
                    ADnumber = iAD
        assert(self.SUCCESS == self.driver.SetADChannel(ADnumber)), "unable to set AD channel to {ADnumber}"
        assert(self.SUCCESS == self.driver.SetHSSpeed(0, HSnumber)), "unable to set HS speed to {HSnumber}"
        print(f"set AD channel {ADnumber} with horizontal speed {HSnumber} ({STemp})")

    def set_integration_time_ms(self, ms):
        self.integration_time_ms = ms
        print(f"setting integration time to {self.integration_time_ms}ms")

        exposure = c_float()
        accumulate = c_float()
        kinetic = c_float()
        assert(self.SUCCESS == self.driver.SetExposureTime(c_float(ms / 1000.0))), "unable to set integration time"
        assert(self.SUCCESS == self.driver.GetAcquisitionTimings(byref(exposure), byref(accumulate), byref(kinetic))), "unable to read acquisition timings"
        print(f"read integration time of {exposure.value:.3f}sec (expected {ms}ms)")

fixture = Fixture()
fixture.open()
