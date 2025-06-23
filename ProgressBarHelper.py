#coding: utf-8

from tqdm import tqdm
import time
import sys
import itertools
import time

class DosSpinner:
    """
    A simple DOS-style spinner for command line applications.
    This spinner can be used to indicate that a process is still running.
    """

    _FRAMES = r"|/-\\"

    def __init__(self, stream=sys.stdout, frames=_FRAMES):
        self._stream = stream
        self._frames = itertools.cycle(frames)
        self._first_frame = False
    
    def spin(self) -> None:
        self._stream.write(next(self._frames))
        self._stream.flush()
        self._stream.write("\b")
        self._stream.flush()

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
