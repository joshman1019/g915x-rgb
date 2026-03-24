"""Startup animations for the G915 X keyboard.

The ARCH animation:
1. Types out A-R-C-H one letter at a time in bright white
2. Flashes the letters blue
3. Builds an Arch Linux pyramid logo from bottom to top
4. Transitions the logo from white to blue
5. Fades out before applying the profile
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

# Arch logo pyramid (bottom row to top)
#        0
#       O P
#      K ; L
#     M , . /
PYRAMID_ROWS = [
    [KEY_BY_NAME[k].address for k in ["M", ",", ".", "/"]],   # bottom
    [KEY_BY_NAME[k].address for k in ["K", ";", "L"]],        # middle
    [KEY_BY_NAME[k].address for k in ["O", "P"]],             # upper
    [KEY_BY_NAME[k].address for k in ["0"]],                  # peak
]
ALL_PYRAMID = [addr for row in PYRAMID_ROWS for addr in row]

WHITE = (0xFF, 0xFF, 0xFF)
BLUE = (0x30, 0x80, 0xFF)
BRIGHT_BLUE = (0x60, 0xB0, 0xFF)
OFF = (0x00, 0x00, 0x00)


def play_arch_animation(kb: G915XBackend) -> None:
    """Play the ARCH startup animation on the keyboard."""
    # Start with all keys off
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.3)

    # --- Phase 1: Type out A-R-C-H ---
    for addr in ARCH_KEYS:
        kb.set_key_color(addr, *WHITE)
        kb.commit()
        time.sleep(0.5)

    time.sleep(0.3)

    # Flash ARCH to blue
    for addr in ARCH_KEYS:
        kb.set_key_color(addr, *BLUE)
        kb.commit()
    time.sleep(0.5)

    # Fade out ARCH text
    for addr in ARCH_KEYS:
        kb.set_key_color(addr, *OFF)
        kb.commit()
    time.sleep(0.3)

    # --- Phase 2: Build pyramid logo bottom-to-top ---
    for row in PYRAMID_ROWS:
        for addr in row:
            kb.set_key_color(addr, *WHITE)
            kb.commit()
        time.sleep(0.35)

    time.sleep(0.4)

    # Transition pyramid white -> blue
    for addr in ALL_PYRAMID:
        kb.set_key_color(addr, *BLUE)
        kb.commit()
    time.sleep(0.4)

    for addr in ALL_PYRAMID:
        kb.set_key_color(addr, *BRIGHT_BLUE)
        kb.commit()
    time.sleep(0.3)

    # Fade out pyramid
    for addr in ALL_PYRAMID:
        kb.set_key_color(addr, *OFF)
        kb.commit()
    time.sleep(0.2)
