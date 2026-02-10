import struct

class EEPROMField:
    def __init__(self, pos, data_type, name):
        self.pos        = pos
        self.data_type  = data_type
        self.name       = name

        self.page       = pos[0]
        self.offset     = pos[1]
        self.length     = pos[2]

EEPROM_FIELDS = [
    ((0,  0, 16), "s", "model"),
    ((0, 16, 16), "s", "serial_number"),
    ((0, 32,  4), "I", "baud_rate"),
    ((0, 36,  1), "?", "has_cooling"),
    ((0, 37,  1), "?", "has_battery"),
    ((0, 38,  1), "?", "has_laser"),
    ((0, 39,  2), "H", "feature_mask"),
    ((0, 41,  2), "H", "slit_um"),
    ((0, 43,  2), "H", "start_integ"),
    ((0, 45,  2), "h", "start_temp"),
    ((0, 47,  1), "B", "start_trigger"),
    ((0, 48,  4), "f", "gain"), 
    ((0, 52,  2), "h", "offset"), 
    ((0, 54,  4), "f", "gain_odd"), 
    ((0, 58,  2), "h", "offset_odd"), 
    ((0, 63,  1), "B", "format"), 
    ((1,  0,  4), "f", "wavecal_c0"),
    ((1,  4,  4), "f", "wavecal_c1"),
    ((1,  8,  4), "f", "wavecal_c2"),
    ((1, 12,  4), "f", "wavecal_c3"),
    ((1, 16,  4), "f", "degCtoDAC_c0"),
    ((1, 20,  4), "f", "degCtoDAC_c1"),
    ((1, 24,  4), "f", "degCtoDAC_c2"),
    ((1, 28,  2), "h", "max_temp"),
    ((1, 30,  2), "h", "min_temp"),
    ((1, 32,  4), "f", "adcToDegC_c0"),
    ((1, 36,  4), "f", "adcToDegC_c1"),
    ((1, 40,  4), "f", "adcToDegC_c2"),
    ((1, 44,  2), "h", "r298"),
    ((1, 46,  2), "h", "beta"),
    ((1, 48, 12), "s", "cal_date"),
    ((1, 60,  3), "s", "cal_tech"),
    ((2,  0, 16), "s", "detector"),
    ((2, 16,  2), "H", "active_pixels_horizontal"),
    ((2, 18,  1), "B", "laser_warmup_sec"),
    ((2, 19,  2), "H", "active_pixels_vertical"),
    ((2, 21,  4), "f", "wavecal_c4"),
    ((2, 25,  2), "H", "actual_pixels_horizontal"),
    ((2, 27,  2), "H", "roi_horiz_start"),
    ((2, 29,  2), "H", "roi_horiz_end"),
    ((2, 31,  2), "H", "roi_vertical_region_1_start"),
    ((2, 33,  2), "H", "roi_vertical_region_1_end"),
    ((2, 35,  2), "H", "roi_vertical_region_2_start"),
    ((2, 37,  2), "H", "roi_vertical_region_2_end"),
    ((2, 39,  2), "H", "roi_vertical_region_3_start"),
    ((2, 41,  2), "H", "roi_vertical_region_3_end"),
    ((0, 43,  2), "H", "startup_integration_time_ms"),
    ((0, 45,  2), "h", "startup_temp_degC"),
    ((2, 43,  4), "f", "linearity_c0"),
    ((2, 47,  4), "f", "linearity_c1"),
    ((2, 51,  4), "f", "linearity_c2"),
    ((2, 55,  4), "f", "linearity_c3"),
    ((2, 59,  4), "f", "linearity_c4"),
    ((3, 12,  4), "f", "laser_power_c0"),
    ((3, 16,  4), "f", "laser_power_c1"),
    ((3, 20,  4), "f", "laser_power_c2"),
    ((3, 24,  4), "f", "laser_power_c3"),
    ((3, 28,  4), "f", "max_laser_mW"),
    ((3, 32,  4), "f", "min_laser_mW"),
    ((3, 36,  4), "f", "excitation_nm_float"),
    ((3, 40,  4), "I", "min_integ"),
    ((3, 44,  4), "I", "max_integ"),
    ((3, 48,  4), "f", "avg_resolution"),
    ((3, 52,  2), "H", "laser_watchdog_sec"),
    ((3, 55,  2), "H", "power_watchdog_sec"),
    ((3, 57,  2), "H", "detector_timeout_sec"),
    ((3, 59,  1), "B", "horizontal_binning_mode"),
    ((3, 60,  1), "B", "startup_scans_to_average"),
    ((3, 61,  1), "B", "xs_sml_attenuator"),
    ((4,  0, 64), "s", "user_data"),
    ((5, 30, 16), "s", "product_configuration"),
    ((5, 63,  1), "B", "subformat"),
    ((8,  0, 16), "s", "laser_password")
]

def get_eeprom_fields():
    fields = {}
    for rec in EEPROM_FIELDS:
        pos, data_type, name = rec
        fields[name] = EEPROMField(pos, data_type, name)
    return fields

def parse_eeprom_pages(pages):
    """ @param pages char[8][64] """
    fields = get_eeprom_fields()
    eeprom = {}
    for name, field in fields.items():
        eeprom[name] = unpack(field.pos, field.data_type, name, pages)
    return eeprom

def unpack(address, data_type, field, pages):
    page       = address[0]
    start_byte = address[1]
    length     = address[2]
    end_byte   = start_byte + length

    if page > len(pages):
        print("error unpacking EEPROM page %d, offset %d, len %d as %s: invalid page (field %s)" % ( 
            page, start_byte, length, data_type, field))
        return

    buf = pages[page]
    if buf is None or end_byte > len(buf):
        print("error unpacking EEPROM page %d, offset %d, len %d as %s: buf is %s (field %s)" % ( 
            page, start_byte, length, data_type, buf, field))
        return

    if data_type == "s":
        # This stops at the first NULL, so is not appropriate for binary data (user_data).
        # OTOH, it doesn't currently enforce "printable" characters either (nor support Unicode).
        unpack_result = ""
        for c in buf[start_byte:end_byte]:
            if c == 0:
                break
            unpack_result += chr(c)
    else:
        unpack_result = 0 
        try:
            unpack_result = struct.unpack(data_type, buf[start_byte:end_byte])[0]
        except:
            print("error unpacking EEPROM page %d, offset %d, len %d as %s" % (page, start_byte, length, data_type))
            return

    return unpack_result
