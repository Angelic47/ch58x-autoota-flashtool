#coding: utf-8

from tqdm import tqdm
import time

def make_progress_callback(size_total, desc="Progress") -> callable:
    """
    Create a progress bar callback for firmware flashing.
    :param size_total: Total size of the firmware to be flashed in bytes.
    :param desc: Description for the progress bar.
    :return: A callback function that updates the progress bar.
    """
    bar = tqdm(
        total=size_total,
        desc=desc,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        dynamic_ncols=True,
        bar_format="{desc}: {percentage:5.1f}% |{bar}| {n_fmt}/{total_fmt} | {rate_fmt} | ETA {remaining}"
    )
    
    def callback(size_sent, _):
        bar.n = size_sent
        bar.refresh()
        if size_sent >= size_total:
            bar.close()

    return callback

def flash_firmware_simulate(size_total=128 * 1024, chunk_size=4096):
    callback = make_progress_callback(size_total)
    sent = 0

    while sent < size_total:
        time.sleep(0.05)
        sent = min(sent + chunk_size, size_total)
        callback(sent, size_total)

if __name__ == "__main__":
    flash_firmware_simulate()
