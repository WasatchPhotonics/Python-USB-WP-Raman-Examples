import usb.core
import xml.etree.ElementTree as ET
import re, math, argparse, json, sys

"""
This script isn't "done," in that it needs to use the bit-level ranges and field
definitions to display a "pretty" explanation of the values read over I2C_PEEK, 
but it's good enough for this morning.
"""

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 3000

class Fixture:
    def __init__(self):
        self.tree = None

        parser = argparse.ArgumentParser(description="Dump FPGA Registers", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--xml", type=str, required=True, help="XML file defining FPGA registers")
        parser.add_argument("--debug", action="store_true", help="display internal debugging info")
        self.args = parser.parse_args()

        self.tree = ET.parse(self.args.xml)
        self.root = self.tree.getroot()
        self.registers = {}

        self.pid = 0x1000
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print(f"No spectrometers found with PID 0x{self.pid:04x}")
            sys.exit(1)

    def pretty_dict(self, d):
        return json.dumps(d, indent=2)

    def debug(self, s):
        if self.args.debug:
            print(f"DEBUG: {s}")

    def parse(self):
        for node in self.root:
            tag = node.tag
            attr = node.attrib
            value = node.text

            if tag == 'register':
                self.parse_register(node)
            else:
                print(f"{tag}: {value}")

    def parse_register(self, register_node):
        reg = { '_max_bit': -1 } # we're going to copy key fields into a new dict
        for node in register_node:
            tag = node.tag
            attr = node.attrib
            value = node.text

            if tag in ['name', 'addr_hex', 'bytes', 'mode', 'desc']:
                reg[tag] = value
            elif tag == 'range':
                reg['range'] = self.parse_range(value)
                reg['_max_bit'] = max(reg['_max_bit'], reg['range']['stop'])
            elif tag == 'field':
                self.parse_field(reg, node)

        if 'bytes' in reg:
            reg['bytes'] = int(reg['bytes'])
        else:
            if reg['_max_bit'] > -1:
                reg['bytes'] = int(math.ceil(reg['_max_bit'] + 1) / 8)
            else:
                raise Exception(f"could not compute bytes for reg {self.pretty_dict(reg)}")

        if 'addr_hex' in reg:
            self.registers[reg['addr_hex']] = reg

    def parse_field(self, reg, field_node):
        field = {}
        if 'fields' not in reg:
            reg['fields'] = {}
        
        for node in field_node:
            tag = node.tag
            attr = node.attrib
            value = node.text

            if tag in ['name', 'desc', 'reset_hex']:
                field[tag] = value
            elif tag == 'range':
                field['range'] = self.parse_range(value)
                reg['_max_bit'] = max(reg['_max_bit'], field['range']['stop'])
            elif tag == 'defs':
                self.parse_defs(field, node)
            else:
                raise Exception(f"unsupported tag {tag} in parse_field")

            reg['fields'][field['name']] = field

    def parse_range(self, s):
        pair = {}
        if re.match(r'^\d+$', s):
            pair['start'] = int(s)
            pair['stop'] = pair['start']
        else:
            m = re.match(r'^(\d+):(\d+)$', s)
            if m:
                pair['stop'] = int(m.group(1))
                pair['start'] = int(m.group(2))
            else:
                raise Exception(f"could not parse range {s}")
        pair['length'] = pair['stop'] - pair['start'] + 1
        return pair

    def parse_defs(self, field, defs_node):
        if 'defs' not in field:
            field['defs'] = {}
        
        value = None
        desc = None
        for node in defs_node:
            tag = node.tag

            if node.tag == 'val_hex':
                value = int(node.text, 16)
            elif node.tag == 'function':
                desc = node.text
            else:
                raise Exception(f"unsupported tag {tag} in parse_defs")

        if value is not None and desc is not None:
            field['defs'][value] = desc


    def peek_all(self):
        for addr_hex, reg in self.registers.items():
            if 'read' in reg['mode'].lower():
                addr_dec = int(addr_hex, 16)
                length = int(reg['bytes'])

                self.debug(f"\nwill peek register {reg['name']} at address 0x{addr_hex} with len {length} bytes")
                if 'fields' in reg:
                    self.debug(f"    and parse the results per {self.pretty_dict(reg['fields'])}")

                try:
                    self.peek(addr=addr_dec, length=length, name=reg['name'])
                except:
                    print(f"ERROR: unable to peek {length} bytes from address 0x{addr_hex}")
        
    def peek(self, addr, length, name=None):
        data = self.get_cmd(0x91, value=addr, index=length, length=length)
        # if addr == 0x12:
        #    ctrl_reg_val = data[1]
        #    ctrl_reg_val <<= 8
        #    ctrl_reg_val |= data[0]
        #    print("Ctrl Reg Val 0x{:04x}".format(ctrl_reg_val))
        data_hex = " ".join( [ f"{v:02x}" for v in data ] )
        print(f"register 0x{addr:02x} [{name}]: 0x{data_hex} ({len(data)} bytes)")
        
    def get_cmd(self, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None):
        result = self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
        value = 0
        if msb_len is not None:
            for i in range(msb_len):
                value = value << 8 | result[i]
            return value
        elif lsb_len is not None:
            for i in range(lsb_len):
                value = (result[i] << (8 * i)) | value
            return value
        else:
            return result

fixture = Fixture()
fixture.parse()
fixture.peek_all()
