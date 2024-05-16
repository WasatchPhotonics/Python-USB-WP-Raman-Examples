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

    # Build dictionary of commands / expected responses based on GUI settings
    if selection == 'BL652':

        if erase:
            erase_cmd_rsp = {"erase": ".*Erasing done.*",
                             "h": ".*FPSCR.*",
                             f"loadfile {cfg['ble']['erase_hex']}": ".*O.K..*",
                             "r": ".*Reset device.",
                             "g": ".* is active.*", }
        else:
            erase_cmd_rsp = {}

        cmd_rsp = {"connect": ".*Type.*",
                   f"{cfg['ble']['part_number']}": ".*cJTAG.*",
                   "S": ".*Default.*",
                   "4000 kHz": "Cortex-M4",
                   **erase_cmd_rsp,
                   "h": ".*FPSCR.*",
                   f"loadfile {cfg['ble']['hex']}": ".*O.K.*",
                   "r": ".*Reset device.*",
                   "g": ".*is active.*",
                   "exit": None}

    if selection == 'STM32':
        cmd_rsp = {"connect": ".*Type.*",
                   f"{cfg['stm']['part_number']}": ".*cJTAG.*",
                   "S": ".*Default.*",
                   "4000 kHz": ".*4000 kHz.*",
                   "h": ".*FPSCR.*",
                   f"loadfile {cfg['stm']['hex']}": ".*O.K..*",
                   "r": ".*Reset device.*",
                   "g": ".*is active.*",
                   "exit": ".OnDisconnectTarget.*"}

    # Spawn a child application
    ps = pexpect.spawn(cfg['jlink']['exe'], encoding='utf-8')

    # Loop through each command / response
    for cmd, rsp in cmd_rsp.items():
        print(f"Sending:\n {cmd}, expecting: {rsp}")
        ps.sendline(cmd)
        if rsp is not None:
            ps.expect(rsp)

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
