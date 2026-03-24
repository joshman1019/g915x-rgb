"""Startup animations for the G915 X keyboard.

The ARCH animation simultaneously:
- Types out A-R-C-H one letter at a time
- Builds the Arch Linux pyramid logo row by row
Both start white, flash blue together, then fade out.
"""

import time

from .backend import G915XBackend
from .keyboard_layout import KEY_BY_NAME

# Key addresses for A-R-C-H text
ARCH_KEYS = [
    KEY_BY_NAME["A"].address,
    KEY_BY_NAME["R"].address,
    KEY_BY_NAME["C"].address,
    KEY_BY_NAME["H"].address,
]

# Arch logo pyramid rows (bottom to top)
#        0
#       O P
#      K ; L
#     M , . /
PYRAMID_ROWS = [
    [KEY_BY_NAME[k].address for k in ["M", "/"]],
    [KEY_BY_NAME[k].address for k in ["K", ";", "L"]],
    [KEY_BY_NAME[k].address for k in ["O", "P"]],
    [KEY_BY_NAME[k].address for k in ["0"]],
]
ALL_PYRAMID = [addr for row in PYRAMID_ROWS for addr in row]

WHITE = (0xFF, 0xFF, 0xFF)
BLUE = (0x30, 0x80, 0xFF)
BRIGHT_BLUE = (0x60, 0xB0, 0xFF)
OFF = (0x00, 0x00, 0x00)


def play_arch_animation(kb: G915XBackend) -> None:
    """Play the ARCH startup animation on the keyboard."""
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.3)

    # 4 beats: each beat lights one ARCH letter + one pyramid row
    for letter_addr, pyramid_row in zip(ARCH_KEYS, PYRAMID_ROWS):
        kb.set_key_color(letter_addr, *WHITE)
        kb.commit()
        for addr in pyramid_row:
            kb.set_key_color(addr, *WHITE)
            kb.commit()
        time.sleep(0.5)

    time.sleep(0.3)

    # Flash everything to blue
    for addr in ARCH_KEYS + ALL_PYRAMID:
        kb.set_key_color(addr, *BLUE)
        kb.commit()
    time.sleep(0.4)

    for addr in ARCH_KEYS + ALL_PYRAMID:
        kb.set_key_color(addr, *BRIGHT_BLUE)
        kb.commit()
    time.sleep(0.3)

    # Fade out
    for addr in ARCH_KEYS + ALL_PYRAMID:
        kb.set_key_color(addr, *OFF)
        kb.commit()
    time.sleep(0.2)
