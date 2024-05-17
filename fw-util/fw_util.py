"""
fw_util.py - Minimal GUI for flashing STM and BLE
"""

import pexpect
import tkinter as tk
import time
import yaml
import logging
import threading

from os.path import isfile

# Setup the logger and connect
logger = logging.getLogger(__name__)

def setup_logger(logger, textbox):
    handler = TextHandler(textbox)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

class TextHandler(logging.Handler):
    def __init__(self, textbox):
        super().__init__()
        self.textbox = textbox

    def emit(self, record):
        msg = self.format(record)
        self.textbox.configure(state='normal')
        self.textbox.insert(tk.END, msg + '\n')
        self.textbox.configure(state='disabled')
        self.textbox.yview(tk.END)


class FlashGUI:

    def __init__(self, root):
        """Initialize the GUI"""

        self.cfg = None

        # Gui elements
        self.root = root
        self.ble_rbutton = None
        self.stm_rbutton = None
        self.txt_log = None
        self.chkbox_erase = None
        self.button_flash = None

        self.erase = None
        self.which_chip = None

        # Configure main window
        self.setup_gui()

        # Configure logging
        setup_logger(logger, self.txt_log)

        # Load configuration and verify that all files exist
        self.load_cfg()
        self.check_cfg()


    def load_cfg(self):
        """Load and validate the configuration file"""
        try:
            with open("config.yaml") as f:
                self.cfg = yaml.load(f, Loader=yaml.loader.SafeLoader)
                logger.debug("Loaded config.yaml.")
        except:
                logger.error("Error loading the config.yaml file.")


    def check_cfg(self):
        """Validate files in cfg"""

        files_to_check = [self.cfg['jlink']['exe'],
                          self.cfg['stm']['app_hex'],
                          self.cfg['ble']['softdevice_hex'],
                          self.cfg['ble']['bootloader_hex'],
                          self.cfg['ble']['dfu_settings_1_hex'],
                          self.cfg['ble']['dfu_settings_2_hex'],
                          self.cfg['ble']['app_hex'],
                          ]
        for f in files_to_check:
            if not isfile(f):
                logger.error(f"File {self.cfg['stm']['app_hex']} not found. Verify path or update .yaml.")
                return

        logger.debug("All files in configuration successfully detected.")

    def setup_gui(self):
        """Build the GUI and bind to functionality"""

        self.root.minsize(300, 100)
        self.root.title("SIG Flasher GUI")

        # Variables to store checkbox/ra                                                                               diobutton states
        self.erase = tk.BooleanVar(value=True)
        self.which_chip = tk.StringVar(value='BL652')

        # GUI elements
        self.ble_rbutton = tk.Radiobutton(self.root, text="BL652", variable=self.which_chip, value='BL652')
        self.stm_rbutton = tk.Radiobutton(self.root, text="STM32", variable=self.which_chip, value='STM32')
        self.txt_log = tk.Text(self.root, height=10, width=40)
        self.chkbox_erase = tk.Checkbutton(self.root, text="Erase", variable=self.erase)
        self.button_flash = tk.Button(self.root, text="Flash", command=lambda: self.flash())

        # Place
        self.ble_rbutton.grid(row=0, column=0, pady=2)
        self.chkbox_erase.grid(row=0, column=1, pady=2)
        self.stm_rbutton.grid(row=1, column=0, pady=2)
        self.button_flash.grid(row=2, column=0, pady=2)
        self.txt_log.grid(row=3, column=0, columnspan=2, pady=2, padx=2)

    def flash(self):
        """Send appropriate commands to the JLinkEXE"""
        # Lambda function generating appropriate command / responses for connecting
        connect_cmd_rsp = lambda pn: {"connect": ".*Type.*",
                                      f"{self.cfg['ble']['part_number']}": ".*cJTAG.*",
                                      "S": ".*Default.*",
                                      "4000 kHz": ".*4000 kHz.*"}

        # Function generating appropriate command / response for loading file
        load_file_cmd_rsp = lambda file: {"h": ".*FPSCR.*",
                                          f"loadfile {file}": ".*O.K..*",
                                          "r": ".*Reset device.",
                                          "g": ".* is active.*", }

        # Build dictionary of commands / expected responses based on GUI settings
        if self.which_chip.get() == 'BL652':
            logger.info(f"Flashing BLE chip ")
            #    If erase is requested, the bootloader and dfu settings
            #    are also reloaded

            if self.erase.get():
                load_soft = load_file_cmd_rsp(self.cfg['ble']['softdevice_hex'])
                load_bootloader = load_file_cmd_rsp(self.cfg['ble']['bootloader_hex'])
                load_dfu_1_settings = load_file_cmd_rsp(self.cfg['ble']['dfu_settings_1_hex'])
                load_dfu_2_settings = load_file_cmd_rsp(self.cfg['ble']['dfu_settings_2_hex'])
                erase_cmd_rsp = {"erase": ".*Erasing done.*",
                                 **load_soft,
                                 **load_bootloader,
                                 **load_dfu_1_settings,
                                 **load_dfu_2_settings}
            else:
                erase_cmd_rsp = {}

            connect_ble = connect_cmd_rsp(self.cfg['ble']['part_number'])
            load_ble_fw = load_file_cmd_rsp(self.cfg['ble']['app_hex'])

            cmd_rsp = {**connect_ble,
                       **erase_cmd_rsp,
                       **load_ble_fw,
                       "exit": None}

        if self.which_chip.get() == 'STM32':
            connect_stm = connect_cmd_rsp(self.cfg['stm']['part_number'])
            load_stm_fw = load_file_cmd_rsp(self.cfg['stm']['app_hex'])

            cmd_rsp = {**connect_stm,
                       **load_stm_fw,
                       "exit": None}

        # Spawn a child application
        ps = pexpect.spawn(self.cfg['jlink']['exe'], encoding='utf-8')

        # Loop through each command / response
        for cmd, rsp in cmd_rsp.items():
            logger.debug(f"Sending: {cmd}, expecting: {rsp}.\n")

            ps.sendline(cmd)
            if rsp is not None:
                ps.expect(rsp)
                logger.info(ps.before)

        time.sleep(1)

        ps.close()

        logger.debug("Flashing completed successfully.")


if __name__ == "__main__":
    root = tk.Tk()
    main_ui = FlashGUI(root)
    root.mainloop()

