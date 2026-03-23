"""Physical layout and key address mapping for the Logitech G915 X.

Key addresses are Logitech HID++ addresses.
Standard keys: HID keycode - 3
Modifiers/G-keys/media: Logitech-specific addresses
Coordinates are in key-unit space where 1 unit = standard 1u key width.
"""

from dataclasses import dataclass


@dataclass
class KeyDef:
    name: str           # Human-readable name
    address: int        # Logitech HID++ address
    x: float            # X position (key units)
    y: float            # Y position (key units)
    w: float = 1.0      # Width (key units)
    h: float = 1.0      # Height (key units)
    group: str = "keys"  # Key group
    label: str = ""     # Display label (if different from name)


def _hid(code: int) -> int:
    """Convert HID Usage Table code to Logitech address."""
    return code - 3


# Key groups for bulk operations
GROUPS = [
    "gkeys", "logo", "indicators", "multimedia",
    "fkeys", "modifiers", "arrows", "numeric",
    "functions", "keys",
]

# === Layout geometry ===
# Standard ANSI full-size: main area is 15u wide
# G915 X adds: G-key column (left), media keys (top-right)

G_W = 1.0           # G-key column width
G_COL = 0.0         # G-key column start X
MAIN_X = 1.25       # Main keyboard area start X (after G-keys + small gap)

# Standard ANSI spacing
NAV_X = MAIN_X + 15.5   # Nav cluster (0.5u gap after main 15u)
NUM_X = NAV_X + 3.5     # Numpad (0.5u gap after nav 3u)

ROW_F = 0.0         # Function row Y
ROW_1 = 1.5         # Number row Y (1.5u gap = visual separation)
ROW_2 = 2.5
ROW_3 = 3.5
ROW_4 = 4.5
ROW_5 = 5.5

G915X_KEYS: list[KeyDef] = [
    # === G-Keys ===
    # G1-G5: left column aligned with rows 1-5
    KeyDef("G1", 0xB4, G_COL, ROW_1, w=G_W, group="gkeys"),
    KeyDef("G2", 0xB5, G_COL, ROW_2, w=G_W, group="gkeys"),
    KeyDef("G3", 0xB6, G_COL, ROW_3, w=G_W, group="gkeys"),
    KeyDef("G4", 0xB7, G_COL, ROW_4, w=G_W, group="gkeys"),
    KeyDef("G5", 0xB8, G_COL, ROW_5, w=G_W, group="gkeys"),
    # G6-G9: smaller keys in function row area
    KeyDef("G6", 0xB9, G_COL, ROW_F, w=0.47, h=0.65, group="gkeys"),
    KeyDef("G7", 0xBA, G_COL + 0.52, ROW_F, w=0.47, h=0.65, group="gkeys"),
    KeyDef("G8", 0xBB, G_COL, ROW_F + 0.72, w=0.47, h=0.65, group="gkeys"),
    KeyDef("G9", 0xBC, G_COL + 0.52, ROW_F + 0.72, w=0.47, h=0.65, group="gkeys"),

    # === Function row ===
    KeyDef("Esc",  _hid(0x29), MAIN_X, ROW_F, group="functions"),

    KeyDef("F1",   _hid(0x3A), MAIN_X + 2.0, ROW_F, group="fkeys"),
    KeyDef("F2",   _hid(0x3B), MAIN_X + 3.0, ROW_F, group="fkeys"),
    KeyDef("F3",   _hid(0x3C), MAIN_X + 4.0, ROW_F, group="fkeys"),
    KeyDef("F4",   _hid(0x3D), MAIN_X + 5.0, ROW_F, group="fkeys"),

    KeyDef("F5",   _hid(0x3E), MAIN_X + 6.5, ROW_F, group="fkeys"),
    KeyDef("F6",   _hid(0x3F), MAIN_X + 7.5, ROW_F, group="fkeys"),
    KeyDef("F7",   _hid(0x40), MAIN_X + 8.5, ROW_F, group="fkeys"),
    KeyDef("F8",   _hid(0x41), MAIN_X + 9.5, ROW_F, group="fkeys"),

    KeyDef("F9",   _hid(0x42), MAIN_X + 11.0, ROW_F, group="fkeys"),
    KeyDef("F10",  _hid(0x43), MAIN_X + 12.0, ROW_F, group="fkeys"),
    KeyDef("F11",  _hid(0x44), MAIN_X + 13.0, ROW_F, group="fkeys"),
    KeyDef("F12",  _hid(0x45), MAIN_X + 14.0, ROW_F, group="fkeys"),

    KeyDef("PrtSc", _hid(0x46), NAV_X, ROW_F, group="functions", label="Prt"),
    KeyDef("ScrLk", _hid(0x47), NAV_X + 1.0, ROW_F, group="functions", label="Scr"),
    KeyDef("Pause", _hid(0x48), NAV_X + 2.0, ROW_F, group="functions", label="Pse"),

    # Media keys (top-right, above numpad)
    KeyDef("Prev",  0x9E, NUM_X, ROW_F, group="multimedia", label="<<"),
    KeyDef("Play",  0x9B, NUM_X + 1.0, ROW_F, group="multimedia", label=">||"),
    KeyDef("Next",  0x9D, NUM_X + 2.0, ROW_F, group="multimedia", label=">>"),
    KeyDef("Mute",  0x9C, NUM_X + 3.0, ROW_F, group="multimedia", label="Mute"),

    # Logo LED
    KeyDef("Logo",  0xD2, MAIN_X + 6.5, ROW_F - 0.55, w=2.0, h=0.4, group="logo"),

    # === Row 1: Number row ===
    KeyDef("`",     _hid(0x35), MAIN_X, ROW_1, group="keys"),
    KeyDef("1",     _hid(0x1E), MAIN_X + 1.0, ROW_1, group="keys"),
    KeyDef("2",     _hid(0x1F), MAIN_X + 2.0, ROW_1, group="keys"),
    KeyDef("3",     _hid(0x20), MAIN_X + 3.0, ROW_1, group="keys"),
    KeyDef("4",     _hid(0x21), MAIN_X + 4.0, ROW_1, group="keys"),
    KeyDef("5",     _hid(0x22), MAIN_X + 5.0, ROW_1, group="keys"),
    KeyDef("6",     _hid(0x23), MAIN_X + 6.0, ROW_1, group="keys"),
    KeyDef("7",     _hid(0x24), MAIN_X + 7.0, ROW_1, group="keys"),
    KeyDef("8",     _hid(0x25), MAIN_X + 8.0, ROW_1, group="keys"),
    KeyDef("9",     _hid(0x26), MAIN_X + 9.0, ROW_1, group="keys"),
    KeyDef("0",     _hid(0x27), MAIN_X + 10.0, ROW_1, group="keys"),
    KeyDef("-",     _hid(0x2D), MAIN_X + 11.0, ROW_1, group="keys"),
    KeyDef("=",     _hid(0x2E), MAIN_X + 12.0, ROW_1, group="keys"),
    KeyDef("Bksp",  _hid(0x2A), MAIN_X + 13.0, ROW_1, w=2.0, group="keys", label="Bk"),

    KeyDef("Ins",   _hid(0x49), NAV_X, ROW_1, group="functions"),
    KeyDef("Home",  _hid(0x4A), NAV_X + 1.0, ROW_1, group="functions", label="Hm"),
    KeyDef("PgUp",  _hid(0x4B), NAV_X + 2.0, ROW_1, group="functions", label="PU"),

    KeyDef("NmLk",  _hid(0x53), NUM_X, ROW_1, group="numeric", label="Nm"),
    KeyDef("Num/",  _hid(0x54), NUM_X + 1.0, ROW_1, group="numeric", label="/"),
    KeyDef("Num*",  _hid(0x55), NUM_X + 2.0, ROW_1, group="numeric", label="*"),
    KeyDef("Num-",  _hid(0x56), NUM_X + 3.0, ROW_1, group="numeric", label="-"),

    # === Row 2: Tab row ===
    KeyDef("Tab",   _hid(0x2B), MAIN_X, ROW_2, w=1.5, group="keys"),
    KeyDef("Q",     _hid(0x14), MAIN_X + 1.5, ROW_2, group="keys"),
    KeyDef("W",     _hid(0x1A), MAIN_X + 2.5, ROW_2, group="keys"),
    KeyDef("E",     _hid(0x08), MAIN_X + 3.5, ROW_2, group="keys"),
    KeyDef("R",     _hid(0x15), MAIN_X + 4.5, ROW_2, group="keys"),
    KeyDef("T",     _hid(0x17), MAIN_X + 5.5, ROW_2, group="keys"),
    KeyDef("Y",     _hid(0x1C), MAIN_X + 6.5, ROW_2, group="keys"),
    KeyDef("U",     _hid(0x18), MAIN_X + 7.5, ROW_2, group="keys"),
    KeyDef("I",     _hid(0x0C), MAIN_X + 8.5, ROW_2, group="keys"),
    KeyDef("O",     _hid(0x12), MAIN_X + 9.5, ROW_2, group="keys"),
    KeyDef("P",     _hid(0x13), MAIN_X + 10.5, ROW_2, group="keys"),
    KeyDef("[",     _hid(0x2F), MAIN_X + 11.5, ROW_2, group="keys"),
    KeyDef("]",     _hid(0x30), MAIN_X + 12.5, ROW_2, group="keys"),
    KeyDef("\\",    _hid(0x31), MAIN_X + 13.5, ROW_2, w=1.5, group="keys"),

    KeyDef("Del",   _hid(0x4C), NAV_X, ROW_2, group="functions"),
    KeyDef("End",   _hid(0x4D), NAV_X + 1.0, ROW_2, group="functions"),
    KeyDef("PgDn",  _hid(0x4E), NAV_X + 2.0, ROW_2, group="functions", label="PD"),

    KeyDef("Num7",  _hid(0x5F), NUM_X, ROW_2, group="numeric", label="7"),
    KeyDef("Num8",  _hid(0x60), NUM_X + 1.0, ROW_2, group="numeric", label="8"),
    KeyDef("Num9",  _hid(0x61), NUM_X + 2.0, ROW_2, group="numeric", label="9"),
    KeyDef("Num+",  _hid(0x57), NUM_X + 3.0, ROW_2, h=2.0, group="numeric", label="+"),

    # === Row 3: Caps Lock row ===
    KeyDef("Caps",  _hid(0x39), MAIN_X, ROW_3, w=1.75, group="indicators"),
    KeyDef("A",     _hid(0x04), MAIN_X + 1.75, ROW_3, group="keys"),
    KeyDef("S",     _hid(0x16), MAIN_X + 2.75, ROW_3, group="keys"),
    KeyDef("D",     _hid(0x07), MAIN_X + 3.75, ROW_3, group="keys"),
    KeyDef("F",     _hid(0x09), MAIN_X + 4.75, ROW_3, group="keys"),
    KeyDef("G",     _hid(0x0A), MAIN_X + 5.75, ROW_3, group="keys"),
    KeyDef("H",     _hid(0x0B), MAIN_X + 6.75, ROW_3, group="keys"),
    KeyDef("J",     _hid(0x0D), MAIN_X + 7.75, ROW_3, group="keys"),
    KeyDef("K",     _hid(0x0E), MAIN_X + 8.75, ROW_3, group="keys"),
    KeyDef("L",     _hid(0x0F), MAIN_X + 9.75, ROW_3, group="keys"),
    KeyDef(";",     _hid(0x33), MAIN_X + 10.75, ROW_3, group="keys"),
    KeyDef("'",     _hid(0x34), MAIN_X + 11.75, ROW_3, group="keys"),
    KeyDef("Enter", _hid(0x28), MAIN_X + 12.75, ROW_3, w=2.25, group="keys", label="Ent"),

    KeyDef("Num4",  _hid(0x5C), NUM_X, ROW_3, group="numeric", label="4"),
    KeyDef("Num5",  _hid(0x5D), NUM_X + 1.0, ROW_3, group="numeric", label="5"),
    KeyDef("Num6",  _hid(0x5E), NUM_X + 2.0, ROW_3, group="numeric", label="6"),

    # === Row 4: Shift row ===
    KeyDef("LShift", 0x69, MAIN_X, ROW_4, w=2.25, group="modifiers", label="Shift"),
    KeyDef("Z",      _hid(0x1D), MAIN_X + 2.25, ROW_4, group="keys"),
    KeyDef("X",      _hid(0x1B), MAIN_X + 3.25, ROW_4, group="keys"),
    KeyDef("C",      _hid(0x06), MAIN_X + 4.25, ROW_4, group="keys"),
    KeyDef("V",      _hid(0x19), MAIN_X + 5.25, ROW_4, group="keys"),
    KeyDef("B",      _hid(0x05), MAIN_X + 6.25, ROW_4, group="keys"),
    KeyDef("N",      _hid(0x11), MAIN_X + 7.25, ROW_4, group="keys"),
    KeyDef("M",      _hid(0x10), MAIN_X + 8.25, ROW_4, group="keys"),
    KeyDef(",",      _hid(0x36), MAIN_X + 9.25, ROW_4, group="keys"),
    KeyDef(".",      _hid(0x37), MAIN_X + 10.25, ROW_4, group="keys"),
    KeyDef("/",      _hid(0x38), MAIN_X + 11.25, ROW_4, group="keys"),
    KeyDef("RShift", 0x6D, MAIN_X + 12.25, ROW_4, w=2.75, group="modifiers", label="Shift"),

    KeyDef("Up",     _hid(0x52), NAV_X + 1.0, ROW_4, group="arrows"),

    KeyDef("Num1",  _hid(0x59), NUM_X, ROW_4, group="numeric", label="1"),
    KeyDef("Num2",  _hid(0x5A), NUM_X + 1.0, ROW_4, group="numeric", label="2"),
    KeyDef("Num3",  _hid(0x5B), NUM_X + 2.0, ROW_4, group="numeric", label="3"),
    KeyDef("NumEnt", _hid(0x58), NUM_X + 3.0, ROW_4, h=2.0, group="numeric", label="Ent"),

    # === Row 5: Bottom row ===
    KeyDef("LCtrl", 0x68, MAIN_X, ROW_5, w=1.25, group="modifiers", label="Ctrl"),
    KeyDef("LGui",  0x6B, MAIN_X + 1.25, ROW_5, w=1.25, group="modifiers", label="Super"),
    KeyDef("LAlt",  0x6A, MAIN_X + 2.5, ROW_5, w=1.25, group="modifiers", label="Alt"),
    KeyDef("Space", _hid(0x2C), MAIN_X + 3.75, ROW_5, w=6.25, group="keys"),
    KeyDef("RAlt",  0x6E, MAIN_X + 10.0, ROW_5, w=1.25, group="modifiers", label="Alt"),
    KeyDef("Fn",    0x6F, MAIN_X + 11.25, ROW_5, w=1.25, group="modifiers"),
    KeyDef("Menu",  _hid(0x65), MAIN_X + 12.5, ROW_5, w=1.25, group="modifiers"),
    KeyDef("RCtrl", 0x6C, MAIN_X + 13.75, ROW_5, w=1.25, group="modifiers", label="Ctrl"),

    KeyDef("Left",  _hid(0x50), NAV_X, ROW_5, group="arrows"),
    KeyDef("Down",  _hid(0x51), NAV_X + 1.0, ROW_5, group="arrows"),
    KeyDef("Right", _hid(0x4F), NAV_X + 2.0, ROW_5, group="arrows"),

    KeyDef("Num0",  _hid(0x62), NUM_X, ROW_5, w=2.0, group="numeric", label="0"),
    KeyDef("Num.",  _hid(0x63), NUM_X + 2.0, ROW_5, group="numeric", label="."),
]

# Build lookup dicts
KEY_BY_NAME: dict[str, KeyDef] = {k.name: k for k in G915X_KEYS}
KEY_BY_ADDRESS: dict[int, KeyDef] = {k.address: k for k in G915X_KEYS}

# Group membership
KEY_GROUPS: dict[str, list[KeyDef]] = {}
for key in G915X_KEYS:
    KEY_GROUPS.setdefault(key.group, []).append(key)

# All valid key addresses
ALL_ADDRESSES: list[int] = [k.address for k in G915X_KEYS]

# Layout bounds for rendering
LAYOUT_WIDTH = NUM_X + 4.25
LAYOUT_HEIGHT = ROW_5 + 1.25
