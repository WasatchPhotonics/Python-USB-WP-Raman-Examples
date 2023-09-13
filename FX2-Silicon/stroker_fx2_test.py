#!/usr/bin/python
import sys
import usb.core
import usb.util
import usb.control
import argparse
import inspect
import time

  
def initUSB():
    devList = usb.core.find(find_all=True)
    for device in devList:
      sys.stdout.write('Decimal VendorID=' + str(device.idVendor) + ' & ProductID=' + str(device.idProduct) + '\n')
      sys.stdout.write('Hexadecimal VendorID=' + hex(device.idVendor) + ' & ProductID=' + hex(device.idProduct) + '\n\n')
      if device.idVendor == 0x24aa and device.idProduct == 0x1000:
        sys.stdout.write('Found Wasatch Spectrometer' + hex(device.idVendor) + ',  ' + hex(device.idProduct) + '\n')
        return  device
        break
    
    return None
        
def getEepromPage(wdev, page):
    if(wdev != None):
        sys.stdout.write('\nGet EEPROM Page ' + hex(page)+'\n');
        rbuf = usb.util.create_buffer(64);
        
        bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE);
        sys.stdout.write('bmReqType is ' + hex(bmReqType) + ' \n' + 'recv buf length is ' + str(len(rbuf)) + ' \n\n');
        wdev.ctrl_transfer(bmReqType,0xff, 0x01, page, rbuf);
        sys.stdout.write('response from device for req = 0xff is \n\n');
        print('[{}]'.format(', '.join(hex(x) for x in rbuf)))

               
def getCodeRevision(wdev):
    if(wdev != None):
        sys.stdout.write('Get Code Revision \n')
        #wdev.set_configuration()
        #cfg = wdev.get_active_configuration()
        #interface = cfg[(0,0)]
        rbuf = usb.util.create_buffer(4);
        
        bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE);
        sys.stdout.write('bmReqType is ' + hex(bmReqType) + ' \n' + 'recv buf length is ' + str(len(rbuf)) + ' \n\n');
        wdev.ctrl_transfer(bmReqType,0xc0, 0x20, 0x00, rbuf);
        sys.stdout.write('response from device for req = 0x81 is \n\n');
        print('[{}]'.format(', '.join(hex(x) for x in rbuf)));

def getFPGARevision(wdev):
    if(wdev != None):
        sys.stdout.write('Get FPGA Revision \n')
        rbuf = usb.util.create_buffer(7);
        
        bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE);
        sys.stdout.write('bmReqType is ' + hex(bmReqType) + ' \n' + 'recv buf length is ' + str(len(rbuf)) + ' \n\n');
        wdev.ctrl_transfer(bmReqType,0xb4, 0x20, 0x00, rbuf);
        sys.stdout.write('response from device for req = 0x81 is \n\n');
        print('[{}]'.format(', '.join(hex(x) for x in rbuf)))
        print(bytes(rbuf).decode('utf-8'));

def getSpectrum(wdev):
    sys.stdout.write('\nGet Spectrum check wdev not null \n');
    if(wdev != None):
        sys.stdout.write('\nGet Spectrum \n');
        #rbuf = usb.util.create_buffer(4);
        bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE);
        sys.stdout.write('bmReqType  is ' + hex(bmReqType) + ' \n');
        wdev.ctrl_transfer(bmReqType,0xad, 0, 0, 0);
        time.sleep(1);
        
        spectrum = wdev.read(0x82, 3904);
        print('[{}]'.format(', '.join(hex(x) for x in spectrum)));

        
def main():
    # loop through devices, printing vendor and product ids in decimal and hex
    wasatchDevice = None
    page = None
    regValue = None
    cmd = None
    
    if(len(sys.argv) > 2):
        cmd = sys.argv[1]
        page = sys.argv[2]
    
    wasatchDevice = initUSB();
    getFPGARevision(wasatchDevice);
    getCodeRevision(wasatchDevice);
    #wasatchDevice.reset();
    #time.sleep(3);    
    

    match cmd:
        case 'e':
            for i in range(100000000):
                getEepromPage(wasatchDevice, int(page, 0));

                           
        
        case 's':
                getSpectrum(wasatchDevice)
    
      
    return 0

#
main();


