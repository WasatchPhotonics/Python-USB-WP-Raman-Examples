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