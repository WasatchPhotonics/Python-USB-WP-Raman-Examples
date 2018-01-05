# Python-USB-WP-Raman-Examples
Python USB examples to demonstrate how to set parameters and retrieve spectra from your WP Raman spectrometer

## Getting Started with Python
The recommended Python environment setup is to install Python XY. Python XY is a free scientific and engineering development software for computations, analysis, and data visualization. And it could not be simplier to setup! Simply download the installer found on [http://python-xy.github.io/](http://python-xy.github.io/) and you will be up and running in minutes! Just be sure to check all of the available plugins during installation.

## WP Raman USB API
We have published a new USB API to make OEM development and instrumentation as easy as possible. A PDF of our API can be found [here](http://wasatchdevices.com/wp-content/uploads/2017/02/OEM-WP-Raman-USB-Interface-Spec-Rev1_4.pdf).

## Drivers
These examples require the use of the libusb drivers found either in your Dash3 installation directory or [right here on Github](https://github.com/WasatchPhotonics/WP_Raman_USB_Drivers).

## Supported Examples

### GetSpectra.py
Retrieves one line of spectra from the instrument. This sends the USB command 0xAD to the device to trigger an acquistion based on the device's current settings.

### GetTest.py
Retrieves an assortment of settings from the device.

### SetTest.py
Retrieves Firmware and FPGA revision, then sets and checks the integration time, gain, and offset of the CCD.

### WriteSpectraToFile.py
Continually runs the GetSpectra.py script once every two seconds. Then saves this information into a CSV file. Time period can be changed by adjusting the sleep function call. 

### ExtTrigger.py
Waits for an external trigger to occur on the connected spectrometer and prints the frame number to the console

### ExtTriggerToFile.py
Waits for an external trigger to occur and then writes each spectra collected into a csv file in the local directory. The optional frame counter must be commented out when opperating at a sampling frequency > 100Hz.

### WriteADCToFile.py
Pulls the raw temperature values of the CCD and the Laser thermistors, displays them in the console, and stores them in a local CSV file. 

### LaserOn.py
Enables the light source on supported devices

### LaserOff.py
Disables the light source on supported devices

### LaserOn_Set_PWR_X.py
Enables the laser and sets the output power to a specified percentage.

### InGaAs Spectrometer Specific

### InGaAs_SetHighGain.py
Places the InGaAs sensor into HIGH_GAIN mode

### InGaAs_SetLowGain.py
Places the InGaAs sensor into LOW_GAIN mode