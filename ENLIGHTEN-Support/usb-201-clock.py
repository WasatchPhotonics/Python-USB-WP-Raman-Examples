
import argparse
import time

def time_ms():
    return 1000*time.time()

def start_clock(period, width):
    startTime = time_ms()

    signal_rise_counts = 0
    signal_fall_counts = 0

    while True:
        elapsed = time_ms() - startTime
        if elapsed // period > signal_rise_counts:
            print(f"[{elapsed}]: GPIO 1")
            signal_rise_counts = elapsed // period
        elif (elapsed - width) // period > signal_fall_counts:
            print(f"[{elapsed}]: GPIO 0")
            signal_fall_counts = (elapsed - width) // period

        # if you try to loop without sleep, the OS will add sleeping, decreasing accuracy
        time.sleep(1e-6)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog = "usb-201 clock",
        description = "generate a sequence of pulses at a regular timed interval"
    )
    parser.add_argument('-p', '--period-ms', dest="period", help="duration between pulse starts")
    parser.add_argument('-w', '--width-ms', dest="width", help="duration of pulses")
    args = parser.parse_args()

    start_clock(float(args.period), float(args.width))