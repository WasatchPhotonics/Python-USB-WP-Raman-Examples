"""
fw_util.py - Minimal GUI for flashing STM and BLE
"""

import pexpect
import tkinter as tk
import time

# Harcoded for now.  Maybe these should move into a config file
JLINK_EXE="/Applications/SEGGER/JLink/JLinkExe"
ERASE_HEX="s132_nrf52_7.0.1_softdevice.hex"
BLE_HEX="170086_sig_ble_nrf_v4.4.0.hex"
STM_HEX="170112_v01_0_17_1_170113_v01_4_15.hex"
BLE_PN="NRF52832_XXAA"
STM_PN="STM32H753VI"

def do_flash(selection, erase):
    """Send appropriate commands to the JLinkEXE"""

    # Build dictionary of commands / expected responses based on GUI settings
    if selection == 'BL652':

        if erase:
            erase_cmd_rsp = {"erase":".*Erasing done.*",
                             "h":".*FPSCR.*",
                             f"loadfile {ERASE_HEX}":".*O.K..*",
                             "r":".*Reset device.",
                             "g":".* is active.*",}
        else:
            erase_cmd_rsp = {}

        cmd_rsp = { "connect" : ".*Type.*",
                    f"{BLE_PN}": ".*cJTAG.*",
                    "S" : ".*Default.*",
                    "4000 kHz":"Cortex-M4",
                    **erase_cmd_rsp,
                    "h": ".*FPSCR.*",
                    f"loadfile {BLE_HEX}" :".*O.K.*",
                    "r": ".*Reset device.*",
                    "g": ".*is active.*",
                    "exit": None}

    if selection == 'STM32':
        cmd_rsp = { "connect" : ".*Type.*",
                    f"{STM_PN}" : ".*cJTAG.*",
                    "S" : ".*Default.*",
                    "4000 kHz" : ".*4000 kHz.*",
                    "h" : ".*J-Link>.*",
                    f"loadfile {STM_HEX}" : f".*O.K..*",
                    "r" : ".*Reset device.*",
                    "g" : ".*is active.*",
                    "exit" : ".OnDisconnectTarget.*"}

    # Spawn a child application
    ps = pexpect.spawn(f"{JLINK_EXE}", encoding='utf-8')

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
    # Create main window
    root = tk.Tk()
    root.title("Firmware flash tool")

    # Variables to store checkbox/radiobutton states
    erase = tk.BooleanVar()
    sel = tk.StringVar()

    # Create buttons
    ble_rbutton = tk.Radiobutton(root, text="BL652", variable=sel, value='BL652')
    stm_rbutton = tk.Radiobutton(root, text="STM32", variable=sel, value='STM32')
    sel.set('BL652')

    chkbox_erase = tk.Checkbutton(root, text="Erase", variable=erase)
    button_flash = tk.Button(root, text="Flash", command= lambda: do_flash(sel.get(), erase.get()))

    #Place
    ble_rbutton.pack()
    chkbox_erase.pack()
    stm_rbutton.pack()
    button_flash.pack()

    # Start the Tkinter event loop
    root.mainloop()

if __name__ == "__main__":
    main()