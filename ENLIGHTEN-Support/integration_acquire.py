#!/usr/bin/env python
################################################################################
#                    integration_acquire.py                                    #
################################################################################
#                                                                              #
#  DESCRIPTION:  Performs two actions on a loop, set_integration_time and      #
#                acquire_spectra.                                              #
#                                                                              #
# Wasatch.PY is used to connect to the device and expose low-level read and    #
# write commands                                                               #
#                                                                              #
# bit-level commands for set_integration_time and acquire_spectra are generated#
# within this program to demostrate that the error does not lie within         #
# Wasatch.PY's command queue, SpectrometerResponse, or other abstractions      #
#                                                                              #
# despite a large timeout of 20sec, the read operation will fail sometimes,    #
# indicating that the device will freeze for a long time                       #
#                                                                              #
# Additional Observations:                                                     #
#     * set_integration_time by itself does not freeze the device              #
#     * set_integration_time uses _send_code which WILL notice if there's an   #
#       error                                                                  #
#     * timeout error occur during acquire_spectra's read                      #
#                                                                              #
#                                                                              #
#  ENVIRONMENT:  (if using Miniconda3)                                         #
#                $ rm -f environment.yml                                       #
#                $ ln -s environments/conda-linux.yml  (or macos, etc)         #
#                $ conda env create -n wasatch3                                #
#                $ conda activate wasatch3                                     #
#  INVOCATION:                                                                 #
#                $ python -u integration_acquire.py                            #
#                                                                              #
################################################################################

import os
import re
import sys
import time
import numpy
import signal
import psutil
import logging
import datetime
import argparse

import wasatch
from wasatch import utils
from wasatch import applog
from wasatch.WasatchBus           import WasatchBus
from wasatch.OceanDevice          import OceanDevice
from wasatch.WasatchDevice        import WasatchDevice
from wasatch.WasatchDeviceWrapper import WasatchDeviceWrapper
from wasatch.RealUSBDevice        import RealUSBDevice

log = logging.getLogger(__name__)

class WasatchDemo(object):

    ############################################################################
    #                                                                          #
    #                               Lifecycle                                  #
    #                                                                          #
    ############################################################################

    def __init__(self, argv=None):
        self.bus     = None
        self.device  = None
        self.logger  = None
        self.outfile = None
        self.exiting = False

        self.logger = applog.MainLogger(logging.DEBUG)
        log.info("Wasatch.PY version %s", wasatch.__version__)

    ############################################################################
    #                                                                          #
    #                              USB Devices                                 #
    #                                                                          #
    ############################################################################

    def connect(self):
        """ If the current device is disconnected, and there is a new device, 
            attempt to connect to it. """

        # if we're already connected, nevermind
        if self.device is not None:
            return

        # lazy-load a USB bus
        if self.bus is None:
            log.debug("instantiating WasatchBus")
            self.bus = WasatchBus(use_sim = False)

        if not self.bus.device_ids:
            print("No Wasatch USB spectrometers found.")
            return 

        device_id = self.bus.device_ids[0]
        log.debug("connect: trying to connect to %s", device_id)
        device_id.device_type = RealUSBDevice(device_id)

        log.debug("instantiating WasatchDevice (blocking)")
        if device_id.vid == 0x24aa:
            device = WasatchDevice(device_id)
        else:
            device = OceanDevice(device_id)

        ok = device.connect()
        if not ok:
            log.critical("connect: can't connect to %s", device_id)
            return

        log.debug("connect: device connected")

        self.device = device
        self.reading_count = 0

        return device

    ############################################################################
    #                                                                          #
    #                               Run-Time Loop                              #
    #                                                                          #
    ############################################################################

    def run(self):
        log.info("Wasatch.PY %s Demo", wasatch.__version__)

        # apply initial settings
        self.device.change_setting("integration_time_ms", 1000)
        self.device.change_setting("scans_to_average", 1)
        self.device.change_setting("detector_tec_enable", True)

        integration_times = [600, 601, 602, 603]
        integration_times_index = 0

        SPAM_integration_times = True

        # read spectra until user presses Control-Break
        while not self.exiting:

            # low-level set integration time
            ms = integration_times[integration_times_index % len(integration_times)]
            ms = max(1, int(round(ms)))
            lsw =  ms        & 0xffff
            msw = (ms >> 16) & 0x00ff
            result = self.device.hardware._send_code(0xB2, lsw, msw, label="SET_INTEGRATION_TIME_MS")
            integration_times_index += 1

            time.sleep(1)

            # low-level acquire reading
            self.device.hardware._send_code(0xad, label="ACQUIRE_SPECTRUM")

            pixels = self.device.settings.pixels()
            block_len_bytes = pixels * 2
            endpoint = 0x82
            if self.device.settings.is_micro():
                # we have no idea if Series-XS has to "wake up" the sensor, so wait
                # long enough for 6 throwaway frames if need be
                timeout_ms = self.device.settings.state.integration_time_ms * 8 + 500 * self.device.settings.num_connected_devices
            else:
                timeout_ms = self.device.settings.state.integration_time_ms * 2 + 1000 * self.device.settings.num_connected_devices
            
            # timeout is usually 580ms
            timeout_ms = 20*1000 # 20 second timeout, to give SIG all the chance to return something

            data = self.device.hardware.device_type.read(self.device.hardware.device, endpoint, block_len_bytes, timeout=timeout_ms)

            time.sleep(1)

        log.debug("WasatchDemo.run exiting")

################################################################################
# main()
################################################################################

def signal_handler(signal, frame):
    print('\rInterrupted by Ctrl-C...shutting down', end=' ')
    clean_shutdown()

def clean_shutdown():
    log.debug("Exiting")
    if demo:
        if demo.device:
            log.debug("closing background thread")
            demo.device.disconnect()

        if demo.logger:
            log.debug("closing logger")
            log.debug(None)
            demo.logger.close()
            time.sleep(1)
            applog.explicit_log_close()
    sys.exit()

demo = None
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    demo = WasatchDemo(sys.argv)
    if demo.connect():
        # Note that on Windows, Control-Break (SIGBREAK) differs from 
        # Control-C (SIGINT); see https://stackoverflow.com/a/1364199
        log.debug("Press Control-Break to interrupt...")
        demo.run()

    clean_shutdown()
