"""Startup animations for the G915 X keyboard.

The ARCH animation types out A-R-C-H one letter at a time in bright white,
pauses, flashes all four letters blue, then transitions to the profile.
"""

import time

from .backend import G915XBackend
from .keyboard_layout import KEY_BY_NAME

# Key addresses for A-R-C-H
ARCH_KEYS = [
    KEY_BY_NAME["A"].address,
    KEY_BY_NAME["R"].address,
    KEY_BY_NAME["C"].address,
    KEY_BY_NAME["H"].address,
]

WHITE = (0xFF, 0xFF, 0xFF)
BLUE = (0x30, 0x80, 0xFF)
OFF = (0x00, 0x00, 0x00)


def play_arch_animation(kb: G915XBackend) -> None:
    """Play the ARCH startup animation on the keyboard."""
    # Start with all keys off
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.3)

    # Type out A - R - C - H one at a time in white
    for addr in ARCH_KEYS:
        kb.set_key_color(addr, *WHITE)
        kb.commit()
        time.sleep(0.5)

    # Brief pause with all four lit white
    time.sleep(0.4)

    # Flash to blue
    for addr in ARCH_KEYS:
        kb.set_key_color(addr, *BLUE)
        kb.commit()
    time.sleep(0.6)

    # Flash brighter
    for addr in ARCH_KEYS:
        kb.set_key_color(addr, 0x60, 0xB0, 0xFF)
        kb.commit()
    time.sleep(0.3)

    # Fade out
    for addr in ARCH_KEYS:
        kb.set_key_color(addr, *OFF)
        kb.commit()
    time.sleep(0.2)
