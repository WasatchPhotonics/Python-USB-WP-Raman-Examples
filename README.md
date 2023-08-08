# Python-USB-WP-Raman-Examples

This repository contains mostly short, single-purpose Python USB utility scripts 
demonstrating specific opcodes and functions on Wasatch Photonics USB 
spectrometers.

These are essentially a random mix of single-purpose one-off functional tests 
used for firmware verification and debugging.  They are not consistently
organized, labeled, documented, or maintained.

They DELIBERATELY eschew re-use (imported private dependencies) in order to 
maintain a "single script contains everything needed" model showing how little is 
required to communicate with the spectrometer over USB.

For more complete and organized information on how to control Wasatch
spectrometers from Python, please see our 
[Wasatch.PY](https://github.com/WasatchPhotonics/Wasatch.PY) repository,
which contains the same back-end driver code used to support our own 
cross-platform ENLIGHTEN&trade; spectroscopy application.

# Wasatch Photonics USB API

The formal USB API supported by our spectrometers is documented in Wasatch 
Photonics' engineering document "ENG-0001 FID (Feature Identification Device)
USB API (Application Programming Interface)", available on our website:

- https://wasatchphotonics.com/technical-resources/

This document is often used in conjunction with "ENG-0034 EEPROM Specification",
hosted at the same link.

# Installation

To use these Python scripts, you may need to install up to five different
software products:

1. Git (unless already installed)
2. Clone the Python-USB-WP-Raman-Examples repository
3. Install Python itself (unless you already have Python 3.7+ installed)
4. Install Python library dependencies (pip packages)
5. libusb .inf files for Wasatch USB devices

## Git Installation

We recommend Git for Windows:

- https://gitforwindows.org/

After installation, open a Git Command shell (looks like a DOS prompt), change
into whatever directory holds your source code projects, and type (HTTPS
example shown):

    C:> git clone https://github.com/WasatchPhotonics/Python-USB-WP-Raman-Examples.git
    C:> cd Python-USB-WP-Raman-Examples

_TODO: add example for creating SSH keys and adding to GitHub profile_

## Python Installation

You can get Python from Python.org here:

- https://www.python.org/downloads/windows/

We recommend the latest "stable / released" 64-bit version, currently
3.10 or 3.11 by platform.

The Python.org distribution will install into /Users/username/AppData/Local/Programs/Python/Python311,
and will not add a program "python.exe" to your path.

However, it will add a "py.exe" to your path, which you should be able to confirm
by opening a DOS or Git Cmd shell and typing:

    C:> where py
    C:\Windows\py.exe
    
    C:> py --version
    Python 3.11.4

## Python Libraries

The following pip modules should allow you to run the majority of scripts
in the repository:

    C:> pip install pyusb libusb matplotlib numpy

## libusb-win32 .inf files

These examples assume that your computer can see and control your spectrometer
via a libusb-compatible driver (appears under "libusb-win32" in Device Manager).
The simplest way to install these drivers is generally to install ENLIGHTEN:

- https://wasatchphotonics.com/enlighten/

Otherwise, see [Wasatch.PY](https://github.com/WasatchPhotonics/Wasatch.PY) for
information on configuring libusb for your platform (remembering to include the
udev rules file for Linux and Raspberry Pi).
