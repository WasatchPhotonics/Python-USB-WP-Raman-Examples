"""
fw_util.py - Minimal GUI for flashing STM and BLE
"""

from platform import system
import tkinter as tk
import time
import yaml
import logging
import threading
from queue import Queue
from os.path import isfile, normpath
import signal

# Import different package on Windows
IS_WINDOWS = system() == 'Windows'

if IS_WINDOWS:
    import pexpect
    import pexpect.popen_spawn
    from pexpect.popen_spawn import PopenSpawn
else:
    from pexpect import spawn



CONFIG_FILE = "config.yaml"
LOG_FILE = "fw_util.log"

# Set up the logger and connect
logger = logging.getLogger(__name__)

class TextHandler(logging.Handler):
    """Custom log hander to send messages to GUI"""

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
    """Class encapsulating program GUI and functionality"""
    def __init__(self, root):

        self.cfg = None
        self.root = root

        # Flag indicating if commands are being sent to JLink program
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

        # Logging to text box is through a custom handler
        gui_handler = TextHandler(self.log_txt)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        logger.addHandler(gui_handler)

        # Logging to file
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

        logger.setLevel(logging.DEBUG)

        # Load configuration and verify that all files exist
        self.load_cfg()
        self.check_cfg()

    def load_cfg(self):
        """Load and validate the configuration file"""
        try:
            with open(CONFIG_FILE) as f:
                self.cfg = yaml.load(f, Loader=yaml.loader.SafeLoader)
                logger.debug("Loaded config.yaml.")

                # Normalize the path to the executable
                # This helps to keep things working across multiple platforms
                self.cfg['jlink']['exe'] = normpath(self.cfg['jlink']['exe'])

                # On Windows we also need to both wrap the path in single quotes (in case it has spaces)
                # And also convert all single to double slashes

                if IS_WINDOWS:
                    self.cfg['jlink']['exe'].replace("\\", r"/")
                    logger.debug(f"Path to exe {self.cfg['jlink']['exe']}")

                # debugging

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

        # Launch the JLink executable
        jlink_exe = self.cfg['jlink']['exe']
        jlink_ps = PopenSpawn(f'"{jlink_exe}"', encoding='utf-8', timeout=5)

        # Load command / responses into a Queue
        cmd_queue = Queue()
        for c in cmd_rsp:
            cmd_queue.put(c)

        self.run_flag = True

        # Loop through the queue of commands and transmit to the Jlink program.
        # For each command sent, check for appropriate response indicating success.
        # Note that on Windows, pexpect doesn't seem to be reading from the stdin stream
        # So we are not able to verify responses as we are in Linux/Mac

        while not cmd_queue.empty() and self.run_flag:
            cmd, rsp, msg = cmd_queue.get()

            try:
                logger.debug(f"Sending: {cmd}, expecting: {rsp}.")

                # If provided, display status message to UI
                if msg is not None:
                    logger.info(msg)

                jlink_ps.sendline(f"{cmd}\r\n")

                time.sleep(3)

                # If expected response is provided, check for it
                if rsp is not None:
                    logger.debug(f"Checking for response: {rsp}")

                    # For Windows, the second option in the expect list is regex for anything

                    if IS_WINDOWS:
                        expected = [rsp, "[\s\S]*", pexpect.TIMEOUT]
                    else:
                        expected = [rsp, pexpect.TIMEOUT]

                    res_index = jlink_ps.expect(expected)

                    # Timeout is never expected
                    if expected[res_index] == pexpect.TIMEOUT:
                        logger.error("Timeout occured while communicating with JLink")

                    logger.debug(f"Result: {jlink_ps.before}\n, expected item found = {expected[res_index]}")

            except Exception as err:
                logger.error(f"Error while flashing. Halting.\n"
                             f"Last command: {cmd}\n"
                             f"Error message: {err}")

                logger.error("Flashing process failed\n")

                break

        # Wait for 10 seconds after sending all the commands to make sure they are processed
        # This is only necessary on Windows since Pexpect does not work as expected.
        if IS_WINDOWS:
            time.sleep(10)
        else:
            jlink_ps.close()

        self.run_flag = False
        self.flash_btn.config(state=tk.ACTIVE)

        logger.info("Flashing process completed successfully.")

    def flash(self):
        """ Send appropriate commands to the JLinkEXE
        """

        # Lambda function generating appropriate command / responses for connecting
        # Stored as a list of lists, where content is: COMMAND, EXPECTED RESPONSE, LOG MESSAGE

        connect_cmd_rsp = lambda pn: [["connect", ".*Type.*", "Connecting to JLink Segger"],
                                      [f"{pn}", ".*cJTAG.*", f"Connecting to {pn}"],
                                      ["S", ".*Default.*", "Setting to SWD"],
                                      ["4000 kHz", ".*4000 kHz.*", "Setting frequency to 4000 kHz"]]

        # Function generating appropriate command / response for loading file

        load_file_cmd_rsp = lambda file: [["h", ".*FPSCR.*", "Halting"],
                                          [f"loadfile {file}", ".*O.K..*", f"Flashing contents of {file}"],
                                          ["r", ".*Reset device.","Resetting the device"],
                                          ["g", ".* is active.*", "Starting the device"]]

        # Build dictionary of commands / expected responses based on GUI settings
        if self.which_chip.get() == 'BL652':

            logger.info(f"Flashing BLE chip.")

       # If erase is requested, the bootloader and dfu settings are also reloaded.

            if self.erase.get():
                load_soft = load_file_cmd_rsp(self.cfg['ble']['softdevice_hex'])
                load_bootloader = load_file_cmd_rsp(self.cfg['ble']['bootloader_hex'])
                load_dfu_1_settings = load_file_cmd_rsp(self.cfg['ble']['dfu_settings_1_hex'])
                load_dfu_2_settings = load_file_cmd_rsp(self.cfg['ble']['dfu_settings_2_hex'])

                erase_cmd_rsp = [["erase", ".*Erasing done.*","Erasing the device"],
                                 *load_soft,
                                 *load_bootloader,
                                 *load_dfu_1_settings,
                                 *load_dfu_2_settings]
            else:
                erase_cmd_rsp = []

            connect_ble = connect_cmd_rsp(self.cfg['ble']['part_number'])
            load_ble_fw = load_file_cmd_rsp(self.cfg['ble']['app_hex'])

            cmd_rsp = [*connect_ble,
                       *erase_cmd_rsp,
                       *load_ble_fw,
                       ["exit", None, None]]

        if self.which_chip.get() == 'STM32':
            logger.info("Flashing STM32")
            connect_stm = connect_cmd_rsp(self.cfg['stm']['part_number'])
            load_stm_fw = load_file_cmd_rsp(self.cfg['stm']['app_hex'])

            cmd_rsp = [*connect_stm,
                       *load_stm_fw,
                       ["exit", None, None]]

        # Spawn a child application for sending/receiving to the JLink executable to enable UI to remain responsive
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
