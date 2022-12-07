# Python-USB-WP-Raman-Examples

This repository contains mostly short, single-purpose Python USB sample scripts 
to demonstrate how to exercise specific opcodes and functions on Wasatch 
Photonics USB spectrometers.

These are essentially a random mix of single-purpose one-off functional tests 
used for firmware verification and debugging.  They are not consistently
organized, labeled, documented, or maintained.

For more complete and organized information on how to control Wasatch
spectrometers from Python, please see our [Wasatch.PY](https://github.com/WasatchPhotonics/Wasatch.PY) repository,
which contains the same back-end driver code used to support our own 
cross-platform ENLIGHTEN&trade; spectroscopy application.

## Getting Started with Python

These scripts are normally used with Python 3.9+ from Miniconda.

Older scripts were originally written and tested with Python 2.7
using PythonXY.

## Wasatch Photonics USB API

The formal USB API supported by our spectrometers is documented in Wasatch 
Photonics' engineering document "ENG-0001 FID (Feature Identification Device)
USB API (Application Programming Interface)", available on our website:

- https://wasatchphotonics.com/technical-resources/

This document is often used in conjunction with "ENG-0034 EEPROM Specification",
hosted at the same link.

## Drivers

These examples assume that your computer can see and control your spectrometer
via a libusb-compatible driver.

The simplest way to install these drivers is generally to install ENLIGHTEN:

- https://wasatchphotonics.com/enlighten/

Otherwise, see [Wasatch.PY](https://github.com/WasatchPhotonics/Wasatch.PY) for
information on configuring libusb for your platform (remembering to include the
udev rules file for Linux and Raspberry Pi).
