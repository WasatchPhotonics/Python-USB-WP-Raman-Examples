#!/usr/bin/env python
################################################################################
#                                settleTime.py                                 #
################################################################################
#                                                                              #
#  DESCRIPTION:  Processes datafiles saved by ENLIGHTEN's Laser Character-     #
#                ization feature and computes laser power settling time.       #
#                                                                              #
#  INVOCATION:   $ ./settleTime.py [options] < data.csv                        #
#                                                                              #
################################################################################

import argparse
import sys

def report(power, readings, secs):
    count = len(readings)
    if count == 0:
        return

    elements = args.mean_elements
    last = readings[-elements:]
    mean = sum(last) / float(len(last))

    sec = 9999 # indicate "never settled"
    stable_count = 0
    for i in range(count - 1, -1, -1):
        value = readings[i]
        delta = abs(value - mean) / mean
        if delta < (args.stability_percentage / 100.0):
            sec = secs[i]
            stable_count += 1

    print("Laser Power %d took %.2f sec to stabilize to %.2f within %s%% (%3d of %3d readings)" % (power, sec, mean, args.stability_percentage, stable_count, len(readings)))
        
    del readings[:]
    del secs[:]

    return sec

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stability-percentage', type=int, default=3)
    parser.add_argument('--mean-elements', type=int, default=5)
    return parser.parse_args()

def main():
    last_laser_power = -1
    readings = []
    secs     = []
    settle_times = []

    for line in sys.stdin:
        values = line.strip().split(',')

        if values[0] == 'time': 
            continue # skip header row

        time                     =       values[ 0]
        ramp_sec                 = float(values[ 1])
        level_sec                = float(values[ 2])
        reading_count            =   int(values[ 3])
        laser_power              =   int(values[ 4])
        detector_temp_raw        =       values[ 5]
        detector_temp_degC       = float(values[ 6])
        laser_temp_raw           =       values[ 7]
        laser_temp_degC          = float(values[ 8])
        secondary_adc_raw        =       values[ 9]
        secondary_adc_calibrated = float(values[10])

        if laser_power != last_laser_power:
            settle_time = report(last_laser_power, readings, secs)
            if settle_time is not None:
                settle_times.append(settle_time)
            last_laser_power = laser_power

        readings.append(secondary_adc_calibrated)
        secs.append(level_sec)

    settle_time = report(last_laser_power, readings, secs)
    if settle_time is not None:
        settle_times.append(settle_time)

    print("\nMax %8.2f, Avg %8.2f" % (max(settle_times), (sum(settle_times) / len(settle_times))))

# script begins here
args = parse_args()
main()
