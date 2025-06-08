import gpiod, gpiodevice
from gpiod.line import Bias, Direction, Edge
import threading
from typing import Callable

# GPIO pins for each button (from top to bottom)
# These will vary depending on platform and the ones
# below should be correct for Raspberry Pi 5.
# Run "gpioinfo" to find out what yours might be.
#
# Raspberry Pi 5 Header pins used by Inky Impression:
#    PIN29, PIN31, PIN36, PIN18.
# These header pins correspond to BCM GPIO numbers:
#    GPIO05, GPIO06, GPIO16, GPIO24.
# These GPIO numbers are what is used below and not the
# header pin numbers.

SW_A = 5
SW_B = 6
SW_C = 16  # Set this value to '25' if you're using a Impression 13.3"
SW_D = 24

BUTTONS = [SW_A, SW_B, SW_C, SW_D]

# These correspond to buttons A, B, C and D respectively
LABELS = ["A", "B", "C", "D"]

class BtnListener:
    def __init__(self, callback: Callable[[str], None]):
        self.callback = callback
        self.running = True

        INPUT = gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP, edge_detection=Edge.FALLING)
        chip = gpiodevice.find_chip_by_platform()
        self.offsets = [chip.line_offset_from_id(id) for id in BUTTONS]
        config = dict.fromkeys(self.offsets, INPUT)
        self.request = chip.request_lines(consumer="spectra6-buttons", config=config)

        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()

    def _watch(self):
        while self.running:
            for event in self.request.read_edge_events():
                index = self.offsets.index(event.line_offset)
                label = LABELS[index]
                self.callback(label)

                gpio_number = BUTTONS[index]
                print(f"Button press detected on GPIO #{gpio_number} label: {label}")

    def stop(self):
        self.running = False
