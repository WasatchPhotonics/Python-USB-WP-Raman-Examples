"""
fw_util.py - Minimal GUI for flashing STM and BLE
"""

import pexpect
import tkinter as tk
import time
import yaml
import logging
import threading
from queue import Queue

from os.path import isfile

# Setup the logger and connect
logger = logging.getLogger(__name__)


class TextHandler(logging.Handler):
    def __init__(self, textbox):
        super().__init__()
        self.textbox = textbox

    def emit(self, record):
        """Send the logging message to the GUI text box

        Note: we only send log level info or error messages to the GUI box.
        """
        msg = self.format(record)

        if record.levelname == 'INFO' or record.levelname == 'ERROR':
            self.textbox.configure(state=tk.NORMAL)
            self.textbox.insert(tk.END, msg + '\n', record.levelname)
            self.textbox.configure(state=tk.DISABLED)
            self.textbox.yview(tk.END)


class FlashGUI:

    def __init__(self, root):

        self.cfg = None
        self.root = root

        self.cmd_queue = Queue()
        self.jlink_ps = None
        self.run_flag = False

        # Gui elements
        self.ble_rbtn = None
        self.stm_rbtn = None
        self.log_txt = None
        self.erase_chk = None
        self.flash_btn = None

        self.erase = None
        self.which_chip = None

        # Configure main window
        self.setup_gui()

        # Configure logging

        # Logging to text box is through a custom handler
        gui_handler = TextHandler(self.log_txt)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        gui_handler.setFormatter(formatter)
        logger.addHandler(gui_handler)

        # Logging to file
        logger.addHandler(logging.FileHandler('fw_util.log'))

        logger.setLevel(logging.DEBUG)

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

        # Variables to store checkbox and radiobutton states
        self.erase = tk.BooleanVar(value=True)
        self.which_chip = tk.StringVar(value='BL652')

        # GUI elements
        self.ble_rbtn = tk.Radiobutton(self.root, text="BL652", variable=self.which_chip, value='BL652')
        self.stm_rbtn = tk.Radiobutton(self.root, text="STM32", variable=self.which_chip, value='STM32')
        self.log_txt = tk.Text(self.root, height=10, width=100)
        self.erase_chk = tk.Checkbutton(self.root, text="Erase", variable=self.erase)
        self.flash_btn = tk.Button(self.root, text="Flash", command=self.flash)

        # Place
        self.ble_rbtn.grid(row=0, column=0, pady=2)
        self.erase_chk.grid(row=0, column=1, pady=2)
        self.stm_rbtn.grid(row=1, column=0, pady=2)
        self.flash_btn.grid(row=2, column=0, pady=2)

        # For the textbox, we can configure different text tags to display differently
        # For now, we configure ERROR tags to appear in read
        self.log_txt.grid(row=3, column=0, columnspan=2, pady=2, padx=2)
        self.log_txt.tag_config("ERROR", foreground='red')
        self.log_txt.tag_config("INFO", foreground='black')

    def run_jlink(self, cmd_rsp):

        # Disable flash button while running
        self.flash_btn.config(state=tk.DISABLED)

        jlink_ps = pexpect.spawn(self.cfg['jlink']['exe'], encoding='utf-8')

        # Load command / responses into queue as tuples
        for k, v in cmd_rsp.items():
            self.cmd_queue.put((k, v))

        self.run_flag = True
        while not self.cmd_queue.empty() and self.run_flag:
            cmd, rsp = self.cmd_queue.get()

            try:
                logger.debug(f"Sending: {cmd}, expecting: {rsp}.\n")
                jlink_ps.sendline(cmd)
                time.sleep(1)
                if rsp is not None:
                    logger.debug(f"checking for response: {rsp}")
                    jlink_ps.expect(rsp)
                    logger.debug(f"{jlink_ps.before}")

            except Exception as err:
                logger.error(f"Error while flashing. Halting.\n"
                             f"Last command: {cmd}\n"
                             f"Error message: {err}.")
                jlink_ps.close()

                logger.error("Flashing process failed.")
                return


        # Close the child process
        jlink_ps.close()

        self.run_flag = False
        self.flash_btn.config(state=tk.ACTIVE)

        logger.info("Flashing process completed succesfully.")

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

            logger.info(f"Flashing BLE chip.")

            #    If erase is requested, the bootloader and dfu settings
            #    are also reloaded.

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
            logger.info("Flashing STM32")
            connect_stm = connect_cmd_rsp(self.cfg['stm']['part_number'])
            load_stm_fw = load_file_cmd_rsp(self.cfg['stm']['app_hex'])

            cmd_rsp = {**connect_stm,
                       **load_stm_fw,
                       "exit": None}

        # Spawn a child application
        if self.run_flag is False:
            logger.debug("Launching JLink run thread.")
            jlink_thread = threading.Thread(target=self.run_jlink, args=(cmd_rsp,))
            jlink_thread.start()
        else:
            logger.error("JLink is already running.  Cannot launch another thread.")


if __name__ == "__main__":
    root = tk.Tk()
    main_ui = FlashGUI(root)
    root.mainloop()
