#!/usr/bin/env python


import sys
import usb.core
import argparse

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
   print("No spectrometer found")
   sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

#parser = argparse.ArgumentParser()
#parser.add_argument("--a", type=lambda x: int(x, 16), help="register address in hex")
#args = parser.parse_args()


MAX77972_NTPRTTH1_REG_ADDR=0x1d1
MAX77972_NTPRTTH2_REG_ADDR=0x1d5
MAX77972_NTPRTTH2_REG_ADDR=0x1d5

regAddr = 0xffff

#if args.a is None:
#   print("specify register address (in hex) to read !!")
#   quit()
#else:
#   regAddr = args.a


def Get_Value(Command, command2, ByteCount, regAddr, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, regAddr, 3, TIMEOUT_MS)

def read_reg(regAddr):
    #print(regAddr)
    data = Get_Value(0xff, 0x76, 3, regAddr)
    # print(data)
    val = 0
    if data[0] != 0:
       print("Flr !! rc", data[0])
    else:
       val = data[2]
       val <<= 8
       val |= data[1]
       #print("{}/0x{:2x} : {}/0x{:04x}".format(regAddr, regAddr, val, val))
       #print("0x{:04x}".format(val))
    return val      

print("nThermCfg: 0x{:04x} \n".format(read_reg(0x1ca)))

print("nProtCfg: 0x{:04x} \n".format(read_reg(0x1d7)))

print("nADCCfg: 0x{:04x} \n".format(read_reg(0x1c9)))



nTPrtTh1_regVal = read_reg(0x1d1)
print("MAX nTPrtTh1: 0x{:04x}".format(nTPrtTh1_regVal))

nTPrtTh2_regVal = read_reg(0x1d5)
print("MAX nTPrtTh2: 0x{:04x}".format(nTPrtTh2_regVal))

jeita_t_room = (nTPrtTh1_regVal >> 0) & 0xf
jeita_t_room_degC = (jeita_t_room * 2.5) + 10
print("JEITA T Room", jeita_t_room_degC, " Deg C")

jeita_t_cool = (nTPrtTh1_regVal >> 4) & 0xf
jeita_t_cool_degC = jeita_t_room_degC - ((jeita_t_cool + 1) * 2.5)
print("JEITA T Cool", jeita_t_cool_degC, " Deg C")

jeita_t_cold1 = (nTPrtTh1_regVal >> 8) & 0xf
jeita_t_cold1_degC = jeita_t_cool_degC - ((jeita_t_cold1 + 1) * 2.5)
print("JEITA T Cold1", jeita_t_cold1_degC, " Deg C")

jeita_t_cold2 = (nTPrtTh1_regVal >> 12) & 0xf
jeita_t_cold2_degC = jeita_t_cold1_degC - ((jeita_t_cold2 + 1) * 2.5)
print("JEITA T Cold2", jeita_t_cold2_degC, " Deg C")


jeita_t_warm = (nTPrtTh2_regVal >> 0) & 0xf
jeita_t_warm_degC = jeita_t_room_degC + ((jeita_t_warm + 1) * 2.5)
print("JEITA T Warm", jeita_t_warm_degC, " Deg C")


jeita_t_hot1 = (nTPrtTh2_regVal >> 4) & 0xf
jeita_t_hot1_degC = jeita_t_warm_degC + ((jeita_t_hot1 + 1) * 2.5)
print("JEITA T Hot1", jeita_t_hot1_degC, " Deg C")

jeita_t_hot2 = (nTPrtTh2_regVal >> 8) & 0xf
jeita_t_hot2_degC = jeita_t_hot1_degC + ((jeita_t_hot2 + 1) * 2.5)
print("JEITA T Hot2", jeita_t_hot2_degC, " Deg C")


jeita_t_tooHot = (nTPrtTh2_regVal >> 12) & 0xf
jeita_t_tooHot_degC = jeita_t_hot2_degC + ((jeita_t_tooHot + 1) * 2.5)
print("JEITA T TooHot", jeita_t_tooHot_degC, " Deg C")




print("\n\n")

nVChgCfg1_regVal = read_reg(0x1cc)
print("MAX nVChgCfg1: 0x{:04x}".format(nVChgCfg1_regVal))

jeita_room_ch_v_s4 = (nVChgCfg1_regVal >> 4) & 0xff
jeita_room_ch_v_mv_s4 = 3400 + (jeita_room_ch_v_s4 * 10)
print("JEITA Room Temp Step 4 Ch V", jeita_room_ch_v_mv_s4, "mV")

jeita_warm_ch_v_s4 = (nVChgCfg1_regVal >> 12) & 0xf
jeita_warm_ch_v_mv_s4 = jeita_room_ch_v_mv_s4 -  (jeita_warm_ch_v_s4 * 10)
print("JEITA Warm Temp Step 4 Ch V", jeita_warm_ch_v_mv_s4, "mV")

jeita_cool_ch_v_s4 = (nVChgCfg1_regVal >> 12) & 0xf
jeita_cool_ch_v_mv_s4 = jeita_room_ch_v_mv_s4 -  (jeita_cool_ch_v_s4 * 10)
print("JEITA Cool Temp Step 4 Ch V", jeita_cool_ch_v_mv_s4, "mV")



nVChgCfg2_regVal = read_reg(0x1cd)
print("MAX nVChgCfg2: 0x{:04x}".format(nVChgCfg2_regVal))

jeita_hot1_ch_v_s4 = (nVChgCfg2_regVal >> 8) & 0xf
jeita_hot1_ch_v_mv_s4 = jeita_warm_ch_v_mv_s4 - (jeita_hot1_ch_v_s4 * 10)
print("JEITA Hot1 Temp Step 4 Ch V", jeita_hot1_ch_v_mv_s4, "mV")

jeita_hot2_ch_v_s4 = (nVChgCfg2_regVal >> 12) & 0xf
jeita_hot2_ch_v_mv_s4 = jeita_hot1_ch_v_mv_s4 - (jeita_hot2_ch_v_s4 * 10)
print("JEITA Hot2 Temp Step 4 Ch V", jeita_hot2_ch_v_mv_s4, "mV")

jeita_cold1_ch_v_s4 = (nVChgCfg2_regVal >> 4) & 0xf
jeita_cold1_ch_v_mv_s4 = jeita_cool_ch_v_mv_s4 - (jeita_cold1_ch_v_s4 * 10)
print("JEITA Cold1 Temp Step 4 Ch V", jeita_cold1_ch_v_mv_s4, "mV")

jeita_cold2_ch_v_s4 = (nVChgCfg2_regVal >> 0) & 0xf
jeita_cold2_ch_v_mv_s4 = jeita_cold1_ch_v_mv_s4 - (jeita_cold2_ch_v_s4 * 10)
print("JEITA Cold2 Temp Step 4 Ch V", jeita_cold2_ch_v_mv_s4, "mV")


nIChgCfg1_regVal = read_reg(0x1ce)
print("MAX nIChgCfg1: 0x{:04x}".format(nIChgCfg1_regVal))

# 10:5 -> 6 bits
jeita_room_ch_i_s0 = (nIChgCfg1_regVal >> 5) & 0x3f
jeita_room_ch_i_ma_s0 = jeita_room_ch_i_s0 * 50
print("JEITA Room Temp Step 0 Ch I", jeita_room_ch_i_ma_s0, "mA")

# 4:0 -> 5 bits
jeita_cool_ch_i_s0 = (nIChgCfg1_regVal >> 0) & 0x1f
jeita_cool_ch_i_ma_s0 = jeita_room_ch_i_ma_s0 - (jeita_cool_ch_i_s0 * 50)
print("JEITA cool Temp Step 0 Ch I", jeita_cool_ch_i_ma_s0, "mA")

# 15:11 -> 5 bits
jeita_warm_ch_i_s0 = (nIChgCfg1_regVal >> 11) & 0x1f
jeita_warm_ch_i_ma_s0 = jeita_room_ch_i_ma_s0 - (jeita_warm_ch_i_s0 * 50)
print("JEITA Warm Temp Step 0 Ch I", jeita_warm_ch_i_ma_s0, "mA")

nIChgCfg2_regVal = read_reg(0x1cf)
print("MAX nIChgCfg2: 0x{:04x}".format(nIChgCfg2_regVal))

# 11:8 -> 4 bits
jeita_hot1_ch_i_s0 = (nIChgCfg1_regVal >> 8) & 0xf
jeita_hot1_ch_i_ma_s0 = jeita_warm_ch_i_ma_s0 - (jeita_hot1_ch_i_s0 * 50)
print("JEITA Hot1 Temp Step 0 Ch I", jeita_hot1_ch_i_ma_s0, "mA")

# 15:11 -> 4 bits
jeita_hot2_ch_i_s0 = (nIChgCfg1_regVal >> 11) & 0xf
jeita_hot2_ch_i_ma_s0 = jeita_hot1_ch_i_ma_s0 - (jeita_hot2_ch_i_s0 * 50)
print("JEITA Hot2 Temp Step 0 Ch I", jeita_hot2_ch_i_ma_s0, "mA")

# 7:4 -> 4 bits
jeita_cold1_ch_i_s0 = (nIChgCfg1_regVal >> 4) & 0xf
jeita_cold1_ch_i_ma_s0 = jeita_cool_ch_i_ma_s0 - (jeita_cold1_ch_i_s0 * 50)
print("JEITA Cold1 Temp Step 0 Ch I", jeita_cold1_ch_i_ma_s0, "mA")

# 3:0 -> 4 bits
jeita_cold2_ch_i_s0 = (nIChgCfg1_regVal >> 0) & 0xf
jeita_cold2_ch_i_ma_s0 = jeita_cold1_ch_i_ma_s0 - (jeita_cold1_ch_i_s0 * 50)
print("JEITA Cold1 Temp Step 0 Ch I", jeita_cold1_ch_i_ma_s0, "mA")


