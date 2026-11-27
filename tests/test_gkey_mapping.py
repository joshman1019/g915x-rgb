from g915x_rgb.reactive import EVDEV_TO_ADDR
from g915x_rgb.keyboard_layout import KEY_BY_NAME


def test_gkey_evdev_mapping():
    expected = {
        183: 0xB4,
        184: 0xB5,
        185: 0xB6,
        186: 0xB7,
        187: 0xB8,
        188: 0xB9,
        189: 0xBA,
        190: 0xBB,
        191: 0xBC,
    }

    for evdev_code, address in expected.items():
        assert EVDEV_TO_ADDR[evdev_code] == address


def test_gkey_mapping_matches_keyboard_layout():
    for number in range(1, 10):
        name = f"G{number}"
        evdev_code = 182 + number

        assert EVDEV_TO_ADDR[evdev_code] == KEY_BY_NAME[name].address
