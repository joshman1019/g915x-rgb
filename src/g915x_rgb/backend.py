"""Direct HID++ communication with the Logitech G915 X keyboard.

Protocol: HID++ 4.2 via /dev/hidraw, using PerKeyBacklightV2 (feature 0x8081).
The keyboard only supports 7-byte (report 0x10) and 20-byte (report 0x11) messages.
Key addresses follow HID Usage Table codes minus 3 offset.
"""

import glob
import os
import select
import time


VENDOR_ID = 0x046D
PRODUCT_ID = 0xC359
DEVICE_INDEX = 0x01  # Keyboard behind Lightspeed receiver
HID_KEYCODE_OFFSET = 3  # Logitech address = HID keycode - 3

# Feature IDs discovered via enumeration
FEATURE_PER_KEY_BACKLIGHT = 0x8081
FEATURE_RGB_EFFECTS = 0x8071
FEATURE_BRIGHTNESS = 0x8040

# PerKeyBacklightV2 function IDs (shifted left 4 bits for byte 3)
FUNC_SET_KEY_COLOR = 0x10     # Function 1: set up to 4 individual keys
FUNC_SET_RANGE = 0x50         # Function 5: set key range to color
FUNC_SET_BATCH = 0x60         # Function 6: set up to 13 keys to same color
FUNC_COMMIT = 0x70            # Function 7: commit/apply changes


class KeyboardNotFoundError(Exception):
    pass


class G915XBackend:
    """Low-level HID++ interface to the G915 X keyboard."""

    def __init__(self):
        self._fd = None
        self._hidraw_path = None
        self._pkb_index = None  # PerKeyBacklight feature index

    @property
    def is_connected(self) -> bool:
        return self._fd is not None

    def connect(self) -> None:
        """Find and open the correct hidraw device (interface 2, vendor HID++)."""
        if self._fd is not None:
            return

        path = self._find_hidraw_device()
        if path is None:
            raise KeyboardNotFoundError(
                "Logitech G915 X not found. Check USB connection and udev rules."
            )

        self._hidraw_path = path
        self._fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)

        # Discover the feature index for PerKeyBacklightV2
        self._pkb_index = self._get_feature_index(FEATURE_PER_KEY_BACKLIGHT)
        if self._pkb_index is None:
            self.disconnect()
            raise KeyboardNotFoundError(
                "PerKeyBacklightV2 feature not found on device."
            )

    def disconnect(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
            self._pkb_index = None

    def _find_hidraw_device(self) -> str | None:
        """Find the hidraw device for interface 2 of the G915 X."""
        for hidraw in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
            name = hidraw.split("/")[-1]
            try:
                uevent_path = os.path.join(hidraw, "device", "uevent")
                with open(uevent_path) as f:
                    uevent = f.read()

                hid_id = ""
                for line in uevent.splitlines():
                    if line.startswith("HID_ID="):
                        hid_id = line.split("=", 1)[1]

                # Match vendor:product
                parts = hid_id.split(":")
                if len(parts) >= 3:
                    vid = int(parts[1], 16)
                    pid = int(parts[2], 16)
                    if vid != VENDOR_ID or pid != PRODUCT_ID:
                        continue

                # Check this is interface 2 (vendor HID++) via resolved sysfs path
                device_real = os.path.realpath(os.path.join(hidraw, "device"))
                usb_iface_uevent = os.path.join(device_real, "..", "uevent")
                usb_iface_uevent = os.path.normpath(usb_iface_uevent)
                with open(usb_iface_uevent) as f:
                    parent_uevent = f.read()

                if "INTERFACE=3/0/0" in parent_uevent:
                    return f"/dev/{name}"

            except (FileNotFoundError, ValueError, IndexError):
                continue

        return None

    def _drain(self) -> None:
        """Read and discard all pending data."""
        while True:
            r, _, _ = select.select([self._fd], [], [], 0.01)
            if not r:
                break
            try:
                os.read(self._fd, 64)
            except (BlockingIOError, OSError):
                break

    def _send(self, data: list[int]) -> None:
        """Send a HID++ message (no response expected)."""
        os.write(self._fd, bytes(data))
        # Quick non-blocking read to prevent buffer buildup
        try:
            r, _, _ = select.select([self._fd], [], [], 0)
            if r:
                os.read(self._fd, 64)
        except (BlockingIOError, OSError):
            pass

    def _send_recv(self, data: list[int], timeout: float = 0.2) -> bytes | None:
        """Send a HID++ message and wait for a response."""
        self._drain()
        os.write(self._fd, bytes(data))
        time.sleep(timeout)
        try:
            r, _, _ = select.select([self._fd], [], [], 0.1)
            if r:
                return os.read(self._fd, 64)
        except (BlockingIOError, OSError):
            pass
        return None

    def _get_feature_index(self, feature_id: int) -> int | None:
        """Query IRoot.getFeature to find the index of a feature."""
        hi = (feature_id >> 8) & 0xFF
        lo = feature_id & 0xFF
        resp = self._send_recv(
            [0x10, DEVICE_INDEX, 0x00, 0x00, hi, lo, 0x00]
        )
        if resp and resp[2] != 0xFF:
            idx = resp[4]
            return idx if idx != 0 else None
        return None

    def set_key_color(self, address: int, r: int, g: int, b: int) -> None:
        """Set a single key color (does not commit)."""
        self._ensure_connected()
        msg = [0x11, DEVICE_INDEX, self._pkb_index, FUNC_SET_KEY_COLOR,
               address, r, g, b] + [0] * 12
        self._send(msg)

    def set_keys_color(self, keys: list[tuple[int, int, int, int]]) -> None:
        """Set multiple key colors. Each entry is (address, r, g, b).
        Sends in batches of 4 per message (function 1 limit).
        Does not commit.
        """
        self._ensure_connected()
        for i in range(0, len(keys), 4):
            batch = keys[i:i + 4]
            msg = [0x11, DEVICE_INDEX, self._pkb_index, FUNC_SET_KEY_COLOR]
            for addr, r, g, b in batch:
                msg.extend([addr, r, g, b])
            msg.extend([0] * (20 - len(msg)))
            self._send(msg)

    def set_range_color(self, start: int, end: int, r: int, g: int, b: int) -> None:
        """Set a range of key addresses to the same color (does not commit)."""
        self._ensure_connected()
        msg = [0x11, DEVICE_INDEX, self._pkb_index, FUNC_SET_RANGE,
               start, end, r, g, b] + [0] * 11
        self._send(msg)

    def set_batch_color(self, addresses: list[int], r: int, g: int, b: int) -> None:
        """Set multiple keys to the same color. Up to 13 per message.
        Does not commit.
        """
        self._ensure_connected()
        for i in range(0, len(addresses), 13):
            batch = addresses[i:i + 13]
            msg = [0x11, DEVICE_INDEX, self._pkb_index, FUNC_SET_BATCH,
                   r, g, b] + batch
            msg.extend([0] * (20 - len(msg)))
            self._send(msg)

    def commit(self) -> None:
        """Commit pending color changes to the keyboard."""
        self._ensure_connected()
        msg = [0x11, DEVICE_INDEX, self._pkb_index, FUNC_COMMIT] + [0] * 16
        self._send(msg)

    # Addresses that don't respond to the range function and need
    # individual set commands. Discovered via protocol testing.
    SPECIAL_ADDRESSES = (
        # Modifier keys (0x63-0x6F range)
        list(range(0x63, 0x70))
        # G-keys (0xB4-0xBC)
        + list(range(0xB4, 0xBD))
        # Media keys (0x94-0x9F)
        + list(range(0x94, 0xA0))
        # Logo and other special LEDs (logo at 0xD2)
        + list(range(0xD0, 0xD8))
    )

    def set_all_keys(self, r: int, g: int, b: int) -> None:
        """Set all keys to a single color and commit."""
        self._ensure_connected()
        from .keyboard_layout import G915X_KEYS

        special = set(self.SPECIAL_ADDRESSES)

        # Standard keys via batch
        standard = [(k.address, r, g, b) for k in G915X_KEYS if k.address not in special]
        for i in range(0, len(standard), 16):
            batch = standard[i:i + 16]
            self.set_keys_color(batch)
            self.commit()

        # Special keys: individual commits
        for key in G915X_KEYS:
            if key.address in special:
                self.set_key_color(key.address, r, g, b)
                self.commit()

    def apply_key_colors(self, key_colors: dict[int, tuple[int, int, int]]) -> None:
        """Apply a dict of {address: (r, g, b)} efficiently.

        Standard keys are batched (4 per message, commit every 16).
        Special keys (modifiers, G-keys, media, logo) need individual
        commits to work reliably on the G915 X.
        """
        special = set(self.SPECIAL_ADDRESSES)

        standard_keys = [(a, *rgb) for a, rgb in key_colors.items() if a not in special]
        special_keys = [(a, *rgb) for a, rgb in key_colors.items() if a in special]

        # Standard keys: batch 4 per message, commit every 16
        for i in range(0, len(standard_keys), 16):
            batch = standard_keys[i:i + 16]
            self.set_keys_color(batch)
            self.commit()

        # Special keys: individual commits required
        for addr, r, g, b in special_keys:
            self.set_key_color(addr, r, g, b)
            self.commit()

    def _ensure_connected(self) -> None:
        if self._fd is None:
            self.connect()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()


# Standard HID Usage Table to Logitech address mapping
def hid_to_logi(hid_keycode: int) -> int:
    """Convert HID Usage Table keycode to Logitech G915 X address."""
    return hid_keycode - HID_KEYCODE_OFFSET


def logi_to_hid(logi_addr: int) -> int:
    """Convert Logitech G915 X address to HID Usage Table keycode."""
    return logi_addr + HID_KEYCODE_OFFSET
