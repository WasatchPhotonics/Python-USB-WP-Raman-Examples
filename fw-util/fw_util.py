"""
fw_util.py - Minimal GUI for flashing STM and BLE
"""

import pexpect
import tkinter as tk
import time
import yaml
from yaml.loader import SafeLoader


def do_flash(cfg, selection, erase):
    """Send appropriate commands to the JLinkEXE"""
    # Lambda function generating appropriate command / responses for connecting
    connect_cmd_rsp = lambda pn: {"connect": ".*Type.*",
                                  f"{cfg['ble']['part_number']}": ".*cJTAG.*",
                                  "S": ".*Default.*",
                                  "4000 kHz": ".*4000 kHz.*"}

    # Function generating appropriate command / response for loading file
    load_file_cmd_rsp = lambda file: {"h": ".*FPSCR.*",
                                      f"loadfile {file}": ".*O.K..*",
                                      "r": ".*Reset device.",
                                      "g": ".* is active.*", }

    # Build dictionary of commands / expected responses based on GUI settings
    if selection == 'BL652':

        #    If erase is requested, the bootloader and dfu settings
        #    are also reloaded
        if erase:
            load_soft = load_file_cmd_rsp(cfg['ble']['softdevice_hex'])
            load_bootloader = load_file_cmd_rsp(cfg['ble']['bootloader_hex'])
            load_dfu_1_settings = load_file_cmd_rsp(cfg['ble']['dfu_settings_1_hex'])
            load_dfu_2_settings = load_file_cmd_rsp(cfg['ble']['dfu_settings_2_hex'])
            erase_cmd_rsp = {"erase": ".*Erasing done.*",
                             **load_soft,
                             **load_bootloader,
                             **load_dfu_1_settings,
                             **load_dfu_2_settings}
        else:
            erase_cmd_rsp = {}

        connect_ble = connect_cmd_rsp(cfg['ble']['part_number'])
        load_ble_fw = load_file_cmd_rsp(cfg['ble']['app_hex'])

        cmd_rsp = {**connect_ble,
                   **erase_cmd_rsp,
                   **load_ble_fw,
                   "exit": None}

    if selection == 'STM32':
        connect_stm = connect_cmd_rsp(cfg['stm']['part_number'])
        load_stm_fw = load_file_cmd_rsp(cfg['stm']['app_hex'])
        cmd_rsp = {**connect_stm,
                   **load_stm_fw,
                   "exit": None}

    # Spawn a child application
    ps = pexpect.spawn(cfg['jlink']['exe'], encoding='utf-8')

    # Loop through each command / response
    for cmd, rsp in cmd_rsp.items():
        print(f"Sending:\n {cmd}, expecting: {rsp}")
        ps.sendline(cmd)
        if rsp is not None:
            ps.expect(rsp)
            print(f"{ps.after}")

    time.sleep(1)

    ps.close()

    print("Done.")


def main():
    # Load the YAML file
    with open("config.yaml") as f:
        cfg = yaml.load(f, Loader=SafeLoader)
        print(cfg)

    # Create main window
    root = tk.Tk()
    root.minsize(300, 100)
    root.title("Firmware flash tool")

    # Variables to store checkbox/radiobutton states
    erase = tk.BooleanVar()
    sel = tk.StringVar()

    # Create buttons
    ble_rbutton = tk.Radiobutton(root, text="BL652", variable=sel, value='BL652')
    stm_rbutton = tk.Radiobutton(root, text="STM32", variable=sel, value='STM32')
    sel.set('BL652')

    chkbox_erase = tk.Checkbutton(root, text="Erase", variable=erase)
    button_flash = tk.Button(root, text="Flash", command=lambda: do_flash(cfg, sel.get(), erase.get()))

    #Place
    ble_rbutton.grid(row=0, column=0, pady=2)
    chkbox_erase.grid(row=0, column=1, pady=2)
    stm_rbutton.grid(row=1, column=0, pady=2)
    button_flash.grid(row=2, column=0, pady=2)

    # Start the Tkinter event loop
    root.mainloop()


if __name__ == "__main__":
    main()
