import usb.core

H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
ZZ = [0] * BUFFER_SIZE
TIMEOUT=1000

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
print(dev)

def Get_Value(Command, ByteCount):
    RetArray = dev.ctrl_transfer(D2H, Command, 0, 0, ByteCount, TIMEOUT)

    # assume result is little-endian
    RetVal = 0
    for i in range(ByteCount):
        RetVal <<= 8
        RetVal  |= RetArray[ByteCount - i - 1]
    return RetVal
    
def Test_Set(SetCommand, GetCommand, SetValue, RetLen):
    FifthByte    = (SetValue >> 32) & 0xff
    SetValueHigh = (SetValue >> 16) & 0xffff
    SetValueLow  =  SetValue        & 0xffff
    ZZ[0] = FifthByte
    Ret = dev.ctrl_transfer(H2D, SetCommand, SetValueLow, SetValueHigh, ZZ, TIMEOUT) 
    if BUFFER_SIZE != Ret:
        return(f"Set 0x{SetCommand:02x} Fail")

    RetValue = Get_Value(GetCommand, RetLen)
    return f"Get {GetCommand:x} {'Success' if SetValue == RetValue else 'Failure'} Txd:0x{SetValue:x} Rxd:0x{RetValue:x}"

def get_fpga_version():
    data = dev.ctrl_transfer(D2H, 0xb4, 0, 0, 7, TIMEOUT)   
    return "".join([chr(c) for c in data])
    
fpga_version = get_fpga_version()
print(f"FPGA Ver {fpga_version}\n")

print("Testing Set Commands")     #  set,  get, value, len
print("Integration Time ", Test_Set(0xb2, 0xbf,    10,   6))
print("CCD Offset       ", Test_Set(0xb6, 0xc4,     0,   2))
print("CCD Gain         ", Test_Set(0xb7, 0xc5, 0x1e7,   2)) # i.e. "FunkyFloat" 1.9
