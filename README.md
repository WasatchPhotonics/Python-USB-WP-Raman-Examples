# Python-USB-WP-Raman-Examples
Python USB examples to demonstrate how to set parameters and retrieve spectra from your WP Raman spectrometer

For more elaborate and complex examples of how to control Wasatch
spectroneters from Python, please also see our 
[Wasatch.PY](https://github.com/WasatchPhotonics/Wasatch.PY) repository,
which contains the same back-end driver code used to support our own 
ENLIGHTEN&trade; spectroscopy application.

## Getting Started with Python
The recommended Python environment setup is to install Python XY. Python XY is a free scientific and engineering development software for computations, analysis, and data visualization. And it could not be simplier to setup! Simply download the installer found on [http://python-xy.github.io/](http://python-xy.github.io/) and you will be up and running in minutes! Just be sure to check all of the available plugins during installation.

## WP Raman USB API
We have published a new USB API to make OEM development and instrumentation as easy as possible. A PDF of our API can be found [here](http://wasatchdevices.com/wp-content/uploads/2017/02/OEM-WP-Raman-USB-Interface-Spec-Rev1_4.pdf).

## Drivers
These examples require the use of the libusb drivers found either in your Dash3 installation directory or [right here on Github](https://github.com/WasatchPhotonics/WP_Raman_USB_Drivers).

## General Examples
----

### ExtTrigger.py
Places the spectrometer into External Triggering Mode, if needed, and waits up to 60 seconds before timing out. When a trigger occurs a frame count is displayed in the prompt and the script will wait for the next trigger.
**Supported Platforms:** WP Raman FX2, WP Raman ARM, WP InGaAs

### ExtTriggerToFile.py
Performs the same function as the script above, however, it streams the collected images into a file titled data.csv
**Supported Platforms:** WP Raman FX2, WP Raman ARM, WP InGaAs

### GetADC.py
Retrieves the raw ADC value for the sensor and streams it into the prompt.
**Supported Platforms:** WP Raman FX2, WP Raman ARM, WP InGaAs

### GetFPGARev.py
Retrieves the revision code for the FPGA.
**Supported Platforms:** WP Raman FX2, WP Raman ARM, WP InGaAs

### GetSpectra.py
Retrieves one line of spectra from the instrument. This sends the USB command 0xAD to the device to trigger an acquistion based on the device's current settings.
**Supported Platforms:** WP Raman FX2, WP Raman ARM, WP InGaAs

### GetTest.py
Retrieves an assortment of settings from the device.
**Supported Platforms:** WP Raman FX2, WP Raman ARM, WP InGaAs

### GetTriggerMode.py
Retrieves the current triggering mode from the device.
**Supported Platforms:** WP Raman FX2, WP InGaAs

### SetIntegrationTime1ms.py
Sets the integration time to 1ms.
**Supported Platforms:** WP Raman FX2, WP Raman ARM, WP InGaAs

### SetTest.py
Retrieves Firmware and FPGA revision, then sets and checks the integration time, gain, and offset of the CCD.
**Supported Platforms:** WP Raman FX2, WP Raman ARM, WP InGaAs

### SetTriggerMode_External.py
Places the spectrometer into External Triggering mode
**Supported Platforms:** WP Raman FX2, WP InGaAs

### SetTriggerMode_Internal.py
Places the spectrometer into Internal Triggering mode
**Supported Platforms:** WP Raman FX2, WP InGaAs

### WriteSpectraToFile.py
Continually runs the GetSpectra.py script once every two seconds. Then saves this information into a CSV file. Time period can be changed by adjusting the sleep function call. 
**Supported Platforms:** WP Raman FX2, WP Raman ARM, WP InGaAs

### WriteADCToFile.py
Pulls the raw temperature values of the CCD and the Laser thermistors, displays them in the console, and stores them in a local CSV file. 
**Supported Platforms:** WP Raman FX2, WP Raman ARM, WP InGaAs


## Laser Module Examples
----

### SetLaserON.py
Enables the light source on supported devices.
**Supported Platforms:** WP Raman FX2, WP Raman ARM

### SetLaserOFF.py
Disables the light source on supported devices.
**Supported Platforms:** WP Raman FX2, WP Raman ARM

### SetLaserPwr_X.py
Enables the laser and sets the output power to a specified percentage.
**Supported Platforms:** WP Raman FX2, WP Raman ARM

### SetLaserMod_4ms_40Hz.py
This is a more complex laser modulation example. This configures the laser to a much longer period in which the laser is ON for 4ms with a period of 25ms. 
**Supported Platforms:** WP Raman FX2, WP Raman ARM

## InGaAs Specific Examples
----

### SetGainHigh.py
Places the InGaAs sensor into HIGH_GAIN mode.

### SetGainLow.py
Places the InGaAs sensor into LOW_GAIN mode

### GetGain.py
Requests the current gain setting
