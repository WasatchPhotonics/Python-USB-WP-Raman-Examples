import math
import argparse

class SRMUtil:
    def __init__(self):
        self.config = {
            532:  { "pn": "SRM2242", "range": [150, 4000], "type": "GAUSSIAN",   "coeffs": [ 0.99747, 3100.6, 1.1573, 2972.1, -3.7168e-6, 0.012864 ] },
            633:  { "pn": "SRM2245", "range": [150, 4000], "type": "GAUSSIAN",   "coeffs": [ 0.95071, 1657.7, 0.95207, 1960.0, 0.000018981, 0.011698 ] },
            785:  { "pn": "SRM2241", "range": [200, 3500], "type": "POLYNOMIAL", "coeffs": [ 0.0971937, 0.000228325,-0.0000000586762, 0.000000000216023, -0.0000000000000977171, 0.0000000000000000115596 ] },
            830:  { "pn": "SRM2246", "range": [110, 3000], "type": "GAUSSIAN",   "coeffs": [ 0.99218,3085.3,0.96188,2323.7,0.00001263,-0.021142 ] },
            1064: { "pn": "SRM2244", "range": [100, 3500], "type": "POLYNOMIAL", "coeffs": [ 0.405953, 5.20345e-4, 5.3039e-7, -6.84463e-10, 2.10286e-13, -2.05741e-17 ] }
        }

        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--laser", type=int, help="nominal excitation wavelength")
        self.args = parser.parse_args()

    def run(self):
        laser = self.args.laser
        if laser not in self.config:
            print("unknown excitation")
            return

        wavenumbers, norms = self.generate(laser)
        for i in range(len(norms)):
            print(f"{i}, {wavenumbers[i]}, {norms[i]:.5f}")

    def generate(self, laser):
        srm = self.config[laser]

        coeffs = srm["coeffs"]
        type_ = srm["type"].lower()
        wavenumbers = list(range(srm["range"][0], srm["range"][1] + 1))

        norms = []
        for cm in wavenumbers:
            value = 0
            if type_ == "polynomial":
                value = coeffs[0] \
                      + coeffs[1] * cm \
                      + coeffs[2] * cm * cm \
                      + coeffs[3] * cm * cm * cm \
                      + coeffs[4] * cm * cm * cm * cm \
                      + coeffs[5] * cm * cm * cm * cm * cm
            elif type_ == "gaussian":
                    term = math.log((((cm - coeffs[3]) * (coeffs[2] * coeffs[2] - 1)) / (coeffs[1] * coeffs[2])) + 1)
                    term *= term
                    term *= -math.log(2) / pow(math.log(coeffs[2]), 2)
                    value = coeffs[0] * math.exp(term) + coeffs[4] * cm + coeffs[5]
            norms.append(value)
        return wavenumbers, norms

util = SRMUtil()
util.run()
