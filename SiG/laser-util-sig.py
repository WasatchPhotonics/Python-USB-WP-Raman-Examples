#!/usr/bin/env python

import os
import re
import sys
import math

from time import sleep
from datetime import datetime

import traceback
import usb.core
import argparse
import struct
import sys

import matplotlib.pyplot as plt

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0

MAX_PAGES = 8
PAGE_SIZE = 64
EEPROM_FORMAT = 8

class Fixture(object):
    def __init__(self):
        self.eeprom_pages = None
        self.subformat = None
        self.dev = None
        self.selected_adc = None
        self.tec_mode = None

        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--acquire-after",       action="store_true", help="acquire after")
        parser.add_argument("--acquire-before",      action="store_true", help="acquire before")
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--enable",              action="store_true", help="enable laser")
        parser.add_argument("--disable-first",       type=bool,           help="automatically disable laser at start", default=True)
        parser.add_argument("--verify",              action="store_true", help="verify setters with getter")
        parser.add_argument("--integration-time-ms", type=int,            help="integration time", default=100)
        parser.add_argument("--mod-enable",          action="store_true", help="enable laser modulation")
        parser.add_argument("--mod-period-us",       type=int,            help="laser modulation pulse period (µs)", default=1000)
        parser.add_argument("--mod-width-us",        type=int,            help="laser modulation pulse width (µs)", default=100)
        parser.add_argument("--pid",                 default="4000",      help="USB PID in hex", choices=["1000", "2000", "4000"])
        parser.add_argument("--raman-delay-ms",      type=int,            help="set laser warm-up delay in Raman Mode (~ms)")
        parser.add_argument("--raman-mode",          type=str,            help="dis/enable raman mode (links firing to integration) (bool)")
        parser.add_argument("--selected-adc",        type=int,            help="set selected adc")
        parser.add_argument("--startline",           type=int,            help="set startline for binning (not laser but hey)")
        parser.add_argument("--stopline",            type=int,            help="set stopline for binning (not laser)")
        parser.add_argument("--optimize-roi",        action="store_true", help="optimize vertical ROI")
        parser.add_argument("--watchdog-sec",        type=int,            help="set laser watchdog (sec)")
        parser.add_argument("--power-attenuator",    type=int,            help="set laser power attenuator (max power control via 8-bit digital potentiometer)")
        parser.add_argument("--pixels",              type=int,            help="number of pixels", default=1952)
        parser.add_argument("--wait-sec",            type=int,            help="delay after setting power (how long to fire laser)")
        parser.add_argument("--scans-to-average",    type=int,            help="scans to average", default=10)
        parser.add_argument("--ramp-power-attenuator", action="store_true", help="ramp laser power attenuator (0 to 255 and back by 10 with 5sec soak)")
        parser.add_argument("--tec-setpoint",        type=int,            help="set the laser TEC setpoint (12-bit range)", default=0x318)
        parser.add_argument("--tec-mode",            type=str,            help="set TEC running mode", choices=['off', 'on', 'auto', 'auto-on'])
        parser.add_argument("--ramp-tec",            action="store_true", help="ramp TEC setpoint min->max->min")
        parser.add_argument("--ramp-tec-step",       type=int,            help="ramp increment", default=200)
        parser.add_argument("--ramp-tec-max",        type=int,            help="ramp max", default=4095)
        parser.add_argument("--ramp-tec-min",        type=int,            help="ramp min", default=0)
        parser.add_argument("--continuous-on-readings", type=int,         help="while taking spectra continuously, fire the laser with an on-time of X measurements")
        parser.add_argument("--continuous-on-sec",   type=int,            help="while taking spectra continuously, fire the laser with an on-time of X seconds")
        parser.add_argument("--continuous-off-sec",  type=int,            help="while taking spectra continuously, fire the laser with an off-time of X seconds")
        parser.add_argument("--timeout-ms",          type=int,            help="default timeout", default=3000)

        self.args = parser.parse_args()

        # convert PID from hex string
        self.pid = int(self.args.pid, 16)

        # find the FIRST connected spectrometer of the given PID
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

        if os.name == "posix":
            self.debug("claiming interface")
            self.dev.set_configuration(1)
            usb.util.claim_interface(self.dev, 0)

    def run(self):
        plt.ion()

        if self.args.disable_first: 
            # made this optional, as it doesn't seem to play well with 1.0.2.9 FW?
            self.set_enable(False)

        self.dump("before")
        if self.args.acquire_before:
            self.take_averaged_measurement()

        # by default, the TEC *should* already be auto
        if self.args.tec_mode is not None:
            self.set_tec_mode(self.args.tec_mode)

        if self.args.tec_setpoint:
            self.set_tec_setpoint(self.args.tec_setpoint)

        if self.args.mod_enable:
            self.set_modulation_params()

        if self.args.ramp_power_attenuator:
            self.do_ramp_power_attenuator()

        if self.args.power_attenuator is not None:
            self.get_power_attenuator()
            self.set_power_attenuator(self.args.power_attenuator)
            self.get_power_attenuator()

        if self.args.watchdog_sec is not None:
            self.set_watchdog_sec(self.args.watchdog_sec)

        if self.args.ramp_tec:
            self.do_ramp_tec()

        if self.args.integration_time_ms is not None:
            self.set_integration_time_ms(self.args.integration_time_ms)

        if self.args.selected_adc is not None:
            self.set_selected_adc(self.args.selected_adc)

        if self.args.raman_delay_ms is not None:
            self.set_raman_delay_ms(self.args.raman_delay_ms)

        if self.args.raman_mode is not None:
            self.set_raman_mode(self.str2bool(self.args.raman_mode))
            
        if self.args.enable:
            if self.args.continuous_off_sec and (self.args.continuous_on_sec or self.args.continuous_on_readings):
                self.perform_continuous_measurements()
            else:
                self.set_enable(True)

        if self.args.startline is not None:
            self.set_startline(self.args.startline)

        if self.args.stopline is not None:
            self.set_stopline(self.args.stopline)           

        if self.args.optimize_roi:
            self.optimize_roi()

        if self.args.acquire_after:
            self.take_averaged_measurement()

        if self.args.wait_sec is not None:
            self.sleep_sec(self.args.wait_sec)

        self.set_enable(False)

        self.dump("after")

    ############################################################################
    # opcodes
    ############################################################################

    def get_firmware_version(self):
        return ".".join(reversed([str(x) for x in self.get_cmd(0xc0)]))

    def get_fpga_version(self):
        return "".join([chr(x) for x in self.get_cmd(0xb4)])

    ### Acquire ###############################################################

    def stomp_first(self, a, count):
        for i in range(count):
            a[i] = a[count]

    def stomp_last(self, a, count):
        for i in range(count):
            a[-(i+1)] = a[-(count+1)]

    def acquire(self):
        timeout_ms = self.args.timeout_ms + self.args.integration_time_ms * 2
        print("sending acquire")
        self.send_cmd(0xad)
        bytes_to_read = self.args.pixels * 2
        print(f"reading {bytes_to_read} bytes")
        data = self.dev.read(0x82, bytes_to_read, timeout=timeout_ms)
        spectrum = []
        for i in range(0, len(data), 2):
            spectrum.append(data[i] | (data[i+1] << 8))

        self.stomp_first(spectrum, 3)
        self.stomp_last(spectrum, 1)

        return spectrum

    def perform_continuous_measurements(self):
        # loop until user hits ctrl-C
        exceptions = 0
        while exceptions < 5:
            time_start = datetime.now()
            time_last_on = None
            time_last_off = None
            readings_on = 0
            firing = False
            frame = 0
            while True:
                try:
                    now = datetime.now()
                    if time_last_on is None or (not firing and (now - time_last_off).total_seconds() >= self.args.continuous_off_sec):
                        print(f"{now} turning laser ON")
                        firing = True
                        time_last_on = now
                        self.set_enable(1)
                    elif firing and ( 
                            ( self.args.continuous_on_sec and (now - time_last_on).total_seconds() >= self.args.continuous_on_sec ) or
                            ( self.args.continuous_on_readings and readings_on >= self.args.continuous_on_readings ) ):
                        print(f"{now} turning laser OFF")
                        firing = False
                        time_last_off = now
                        readings_on = 0
                        self.set_enable(0)
                    else:
                        if firing:
                            elapsed = (now - time_last_on).total_seconds()
                            msg = f"laser has been ON for {readings_on} readings ({elapsed:.2f} sec)"
                            readings_on += 1
                        else:
                            elapsed = (now - time_last_off).total_seconds()
                            msg = f"laser has been OFF for {elapsed:.2f} sec"
                        battery = self.get_battery_state()
                        print(f"{now} reading frame {frame} ({msg}, {battery})")
                        spectrum = self.acquire()
                        frame += 1
                except Exception as ex:
                    exceptions += 1
                    print(f"ignoring exception number {exceptions}: {ex}")
        self.set_enable(0)
        print(f"Test completed after {(datetime.now() - time_start).total_seconds()} sec")

    ### Enabled ###############################################################
        
    def get_enable(self):
        return 0 != self.get_cmd(0xe2)[0]

    def set_enable(self, flag):
        print(f"{datetime.now()} setting laserEnable {'ON' if flag else 'OFF'}")
        self.send_cmd(0xbe, 1 if flag else 0)
        if self.args.verify:
            check = self.get_enable()
            if check != flag:
                print(f"ERROR *** set_enable sent {flag}, get_enable read {check}")

    ### Laser Power Attenuator ################################################

    def get_power_attenuator(self):
        value = self.get_cmd(0x83, msb_len=1)
        print(f"laser power attenuator is 0x{value:02x}")
        return value

    def set_power_attenuator(self, value):
        value &= 0xff
        print(f"setting laser power attenuator to 0x{value:02x}")
        self.set_enable(False)
        self.send_cmd(0x82, value)
        self.set_enable(True)

    def do_ramp_power_attenuator(self):
        for i in range(0, 255, 32):
            self.set_power_attenuator(i)
            self.sleep_sec(self.args.wait_sec)
        for i in range(255, -1, -32):
            self.set_power_attenuator(i)
            self.sleep_sec(self.args.wait_sec)

    ### Laser TEC #############################################################

    def set_tec_mode(self, mode):
        mode = mode.lower()
        choices = ['off', 'on', 'auto', 'auto-on']
        value = choices.index(mode)
            
        print(f"setting TEC mode {mode} (value 0x{value:02x})")
        self.send_cmd(0x84, value)
        self.tec_mode = mode

    def do_ramp_tec(self):
        lo = self.args.ramp_tec_min
        hi = self.args.ramp_tec_max
        step = self.args.ramp_tec_step

        self.set_enable(True)
        for dac in range(lo, hi+1, step):
            self.set_tec_setpoint(dac)
            self.sleep_sec(self.args.wait_sec)

        for dac in range(hi, lo-1, -1 * step):
            self.set_tec_setpoint(dac)
            self.sleep_sec(self.args.wait_sec)

        self.set_enable(False)
        sys.exit(0)
            
    def set_tec_setpoint(self, dac):
        dac = min(0xfff, max(0, int(round(dac))))
        print(f"setting LASER_TEC_SETPOINT 0x{dac:02x}")
        self.send_cmd(0xe7, dac)

    ### ADC ###################################################################

    def get_selected_adc(self):
        return self.get_cmd(0xee)[0]

    def set_selected_adc(self, n):
        if not n in (0, 1):
            print("ERROR: selectedADC requires 0 or 1")
            return

        if self.selected_adc is not None and self.selected_adc == n:
            return

        # print("setting selectedADC to %d" % n)
        self.send_cmd(0xed, n)
        self.selected_adc = n

        # stabilization throwaways
        for i in range(2):
            self.get_adc()

    def get_adc(self, n=None):
        if n is not None:
            self.set_selected_adc(n)
        return self.get_cmd(0xd5, lsb_len=2) & 0xfff

    ### Laser Thermistor ######################################################

    def get_laser_thermistor_raw(self):
        return self.get_adc(0)

    def get_laser_thermistor_degC(self, raw=None):
        """
        @see  docs in wasatch.FID.get_laser_thermistor_degC
        @note we're not actually reading the thermistor here, we're reading the 
              TEC IC's "buffered copy" of the thermistor value (likely different
              than the original), and it is likely this calibration is invalid;
              however it may still be USEFUL, so we're giving it a try
        """
        if raw is None:
            raw = self.get_laser_thermistor_raw()

        try:
            degC = 0
            voltage    = 2.5 * raw / 4096
            resistance = 21450.0 * voltage / (2.5 - voltage) 

            if resistance < 0:
                print(f"get_laser_temperature_degC: can't compute degC: raw 0x{raw:04x}, voltage = {voltage}, resistance = {resistance}")
                return -999

            logVal     = math.log(resistance / 10000.0)
            insideMain = logVal + 3977.0 / (25 + 273.0)
            degC       = 3977.0 / insideMain - 273.0
        except:
            degC = -998

        return degC

    ### ViTEC (correlates to TEC current) #####################################

    def get_laser_vitec_raw(self):
        return self.get_adc(1)
    
    ### Integration Time ######################################################

    def get_integration_time_ms(self):
        data = self.get_cmd(0xbf)
        return data[0] + (data[1] << 8) + (data[2] << 16)

    def set_integration_time_ms(self, n):
        # don't worry about 24-bit values
        if n < 1 or n > 0xffff:
            print("ERROR: integrationTimeMS requires positive uint16")
            return

        print("setting integrationTimeMS to %d" % n)
        self.send_cmd(0xb2, n)

    ### Modulation Enable #####################################################

    def get_modulation_enable(self):
        return self.get_cmd(0xe3)[0]

    def set_modulation_enable(self, flag):
        print("setting laserModulationEnable to %s" % ("on" if flag else "off"))
        self.send_cmd(0xbd, 1 if flag else 0)

    def set_modulation_params(self):
        if not self.args.mod_enable:
            return

        if self.args.mod_period_us > 0xffff or \
           self.args.mod_width_us > 0xffff:
            print("error: lame script doesn't support full 40-bit 5-byte args")
            return

        # should we modulate after all?
        if self.args.mod_period_us <= self.args.mod_width_us:
            print("disabling modulation because period %d <= width %d" % (self.args.mod_period_us, self.args.mod_width_us))
            self.set_modulation_enable(False)
            return

        print("setting LASER_MOD_PULSE_PERIOD %d" % self.args.mod_period_us)
        self.send_cmd(0xc7, self.args.mod_period_us, buf=[0]*8)

        print("setting LASER_MOD_PULSE_WIDTH %d" % self.args.mod_width_us)
        self.send_cmd(0xdb, self.args.mod_width_us, buf=[0]*8)

        self.set_modulation_enable(True)

    ### Raman Mode ############################################################

    def get_raman_mode(self):
        if not self.is_sig():
            return
        return self.get_cmd(0xff, 0x15)[0]

    def set_raman_mode(self, flag):
        if not self.is_sig():
            return
        print("setting Raman Mode %s" % ("on" if flag else "off"))
        self.send_cmd(0xff, 0x16, 1 if flag else 0)

    ### Raman Delay ###########################################################

    def get_raman_delay_ms(self):
        if not self.is_sig():
            return
        return self.get_cmd(0xff, 0x19)[0]

    def set_raman_delay_ms(self, ms):
        if not self.is_sig():
            return
        if ms < 0 or ms > 0xffff:
            print("ERROR: raman delay requires uint16")
            return

        print("setting Raman Delay %d ms" % ms)
        self.send_cmd(0xff, 0x20, ms)

    ### Watchdog ###############################################################

    def get_watchdog_sec(self):
        if not self.is_sig():
            return
        data = self.get_cmd(0xff, 0x17)
        #return data[0] + (data[] << 8)
        return data

    def set_watchdog_sec(self, sec):
        if not self.is_sig():
            print(f"set_watchdog_sec: skipping because not SiG")
            return
        if sec < 0 or sec > 0xffff:
            print("ERROR: watchdog requires uint16")
            return

        print("setting Raman Watchdog %d sec" % sec)
        self.send_cmd(0xff, 0x18, sec)

    ### Start Line #############################################################

    def get_startline(self):
        if not self.is_sig():
            return
        data = self.get_cmd(0xff, 0x22)
        return data[0] + (data[1] << 8)

    def set_startline(self, linenum):
        if not self.is_sig():
            return
        if linenum < 0 or linenum > 1078:
            print("ERROR: choose a line between 0 and 1078")
            return

        print("setting startline to %d" % linenum)
        self.send_cmd(0xff, 0x21, linenum)  


    ### Stop Line ##############################################################

    def get_stopline(self):
        if not self.is_sig():
            return
        data = self.get_cmd(0xff, 0x24)
        return data[0] + (data[1] << 8)

    def set_stopline(self, linenum):
        if not self.is_sig():
            return
        if linenum < 2 or linenum > 0x0438:
            print("ERROR: choose a line between 2 and 1080")
            return

        print("setting stopline to %d" % linenum)
        self.send_cmd(0xff, 0x23, linenum)  

    ### Optimize Start/Stop ####################################################

    def take_averaged_measurement(self):
        spectrum = self.acquire()
        for i in range(2, self.args.scans_to_average):
            tmp = self.acquire()
            for j in range(len(spectrum)):
                spectrum[j] += tmp[j]
        for i in range(len(spectrum)):
            spectrum[i] /= self.args.scans_to_average

        plt.plot(spectrum)
        plt.draw()
        plt.pause(0.0001)
        plt.clf()

        return spectrum

    def measure_intensity(self):
        if self.args.enable:
            self.set_enable(False)
            dark = self.take_averaged_measurement()
            self.set_enable(True)
            signal = self.take_averaged_measurement()
            self.set_enable(False)
            for i in range(len(signal)):
                signal[i] -= dark[i]
        else:
            signal = self.take_averaged_measurement()
            
        return sum(signal)

    def optimize_roi(self):
        start = 50
        stop = 1050

        self.set_startline(start)
        self.set_stopline(stop)

        full = self.measure_intensity()
        thresh = full / 5.0
        print(f"full {full} (thresh {thresh})")

        # optimize start
        while True:
            if start + 50 >= stop:
                print(f"can't exceed start {start} due to stop {stop}")
                break
            start += 50
            self.set_startline(start)
            after = self.measure_intensity()
            delta = full - after
            print(f"start {start} = after {after} (delta {delta})")
            if delta > thresh:
                print(f"found good start {start}")
                break
        new_start = start

        # optimize stop
        start = 50
        self.set_startline(start)
        while True:
            if stop - 50 <= start:
                print(f"can't exceed stop {stop} due to start {start}")
                break
            stop -= 50
            self.set_stopline(stop)
            after = self.measure_intensity()
            delta = full - after
            print(f"stop {stop} = after {after} (delta {delta})")
            if delta > thresh:
                print(f"found good stop {stop}")
                break

        start = new_start
        self.set_startline(start)
        self.set_stopline(stop)
        intensity = self.measure_intensity()
        print(f"optimized ROI ({start}, {stop})")
        print(f"full {full}, roi {intensity}")

    ### Battery ################################################################

    def get_battery_state(self):
        if not self.is_sig():
            return

        raw = self.get_cmd(0xff, 0x13)

        charging = 0 != raw[2]
        perc_lsb = raw[0]
        perc_msb = raw[1]

        perc = perc_msb + (1.0 * perc_lsb / 256.0)

        return "%.2f%% (%s)" % (perc, "charging" if charging else "discharging")

    def dump(self, label):
        print("%s:" % label)
        print("    Firmware:            %s" % self.get_firmware_version())
        print("    FPGA:                %s" % self.get_fpga_version())
        print("    Battery State:       %s" % self.get_battery_state())
        print("    Laser enabled:       %s" % self.get_enable())
        print("    Selected ADC:        %s" % self.get_selected_adc())
        print("    Integration Time ms: %s" % self.get_integration_time_ms())
        print("    Watchdog sec:        %s" % self.get_watchdog_sec())
        # print("    Modulation enabled:  %s" % self.get_modulation_enable())
        # print("    Raman Mode:          %s" % self.get_raman_mode())
        # print("    Raman Delay ms:      %s" % self.get_raman_delay_ms())
        # print("    Start line:          %s" % self.get_startline())
        # print("    Stop line:           %s" % self.get_stopline())

    ############################################################################
    # Utility Methods
    ############################################################################

    def is_arm(self):
        return self.pid == 0x4000

    def is_sig(self):
        return self.is_arm() # close enough

    def str2bool(self, s):
        return s.lower() in ("true", "yes", "on", "enable", "1")

    def debug(self, msg):
        if self.args.debug:
            print("DEBUG: %s" % msg)

    def send_cmd(self, cmd, value=0, index=0, buf=None):
        if buf is None:
            if self.is_arm():
                buf = [0] * 8
            else:
                buf = ""
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, self.args.timeout_ms)

    def get_cmd(self, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None):
        result = self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, self.args.timeout_ms)

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

    def sleep_sec(self, sec):
        if self.pid != 0x4000:
            sleep(sec)
            return

        # monitor battery and thermistor while sleeping
        start = datetime.now()
        elapsed_sec = (datetime.now() - start).total_seconds()
        while elapsed_sec < sec:
            remaining = sec - elapsed_sec
            bat = self.get_battery_state()
            therm = self.get_laser_thermistor_raw()
            degC = self.get_laser_thermistor_degC(therm)
            vitec = self.get_laser_vitec_raw()
            print(f"{datetime.now()} battery {bat}, viTEC 0x{vitec:03x}, therm 0x{therm:03x} ({degC:.2f}C), {round(remaining)}sec remaining")
            sleep(min(1, remaining))
            elapsed_sec = (datetime.now() - start).total_seconds()

fixture = Fixture()
if fixture.dev:
    try:
        fixture.run()
    except Exception as ex:
        print(f"caught {ex}")
    fixture.set_enable(False)
