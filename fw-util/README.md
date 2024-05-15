
# JLink FW Flashing Tool
Provides a minimal GUI for flashing STM and BLE chipsets.

# How to install and use
1. Clone project locally: `git clone https://github.com/WasatchPhotonics/Python-USB-WP-Raman-Examples.git`
2. Create and activate virtual environment under the `fw-util/` directory
   1.  `cd fw-util`
   2.  `python -m venv venv`
   3. `. venv/bin/activate`
3. Install dependencies
   1.   `pip install .`
4. Launch GUI
   1.   `python fw_util.py`
5. Connect Segger JLink to appropriate pins
6. Select whether to flash `BLE652` or `STM32`. For `BLE652` there is an optional erase checkbox that will erase it first.
7. Click the `Flash` button and watch the magic happen.

# How to build into an executable
1. Activate your virtual environment and install optional dependencies (only need to do 1x)
   1. `. venv/bin/activate`
   2. `pip install '.[build_exe]'`
2. Build with pyinstaller 
   1. `pyinstaller fw_util.py --onefile`

# Requirements
- JLink `https://www.segger.com/downloads/jlink/` (tested with V7.6G)