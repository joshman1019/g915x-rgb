"""Watch for keyboard (re)connection and apply the saved profile.

Checks for the G915 X by looking for its hidraw sysfs entry WITHOUT
opening the device. Only opens the device briefly when applying a profile.
"""

import glob
import os
import sys
import time

from .animation import play_arch_animation
from .backend import G915XBackend, KeyboardNotFoundError, VENDOR_ID, PRODUCT_ID
from .config import get_last_profile
from .profile import Profile, create_default_profile, load_all_profiles

POLL_INTERVAL = 2  # seconds between checks
SETTLE_DELAY = 2   # seconds to wait after detecting device before applying


def device_present() -> bool:
    """Check if the G915 X is connected by reading sysfs, without opening the device."""
    for hidraw in glob.glob("/sys/class/hidraw/hidraw*"):
        try:
            uevent_path = os.path.join(hidraw, "device", "uevent")
            with open(uevent_path) as f:
                uevent = f.read()
            for line in uevent.splitlines():
                if line.startswith("HID_ID="):
                    parts = line.split("=", 1)[1].split(":")
                    if len(parts) >= 3:
                        vid = int(parts[1], 16)
                        pid = int(parts[2], 16)
                        if vid == VENDOR_ID and pid == PRODUCT_ID:
                            return True
        except (FileNotFoundError, ValueError, IndexError):
            continue
    return False


def find_profile(name: str | None) -> Profile:
    profiles = load_all_profiles()
    if name:
        for p in profiles:
            if p.name.lower() == name.lower():
                return p
    if profiles:
        return profiles[0]
    return create_default_profile()


def apply_once(retries: int = 3) -> bool:
    """Open device, apply profile, close device. Returns True on success.

    Retries on PermissionError since udev rules may not have applied yet
    when the device first appears.
    """
    profile_name = get_last_profile()
    profile = find_profile(profile_name)

    for attempt in range(retries):
        try:
            kb = G915XBackend()
            kb.connect()
            if profile.startup_animation:
                play_arch_animation(kb)
            colors = profile.get_all_key_colors()
            kb.set_all_keys(0, 0, 0)
            time.sleep(0.1)
            kb.apply_key_colors(colors)
            kb.disconnect()
            print(f"Applied profile: {profile.name}")
            return True
        except KeyboardNotFoundError:
            return False
        except PermissionError:
            print(f"Permission denied (attempt {attempt + 1}/{retries}), "
                  "waiting for udev rules...")
            time.sleep(2)
        except Exception as e:
            print(f"Error applying profile: {e}", file=sys.stderr)
            return False
    return False


def main():
    print("g915x-rgb watcher: monitoring for keyboard connection...")
    was_present = False
    applied = False

    while True:
        present = device_present()

        if present and not was_present:
            # Keyboard just appeared — wait for USB enumeration to fully settle
            print("Keyboard detected, waiting for device to settle...")
            time.sleep(SETTLE_DELAY)
            applied = apply_once()

        elif present and not applied:
            # Device present but previous apply failed, retry
            applied = apply_once()

        elif not present and was_present:
            print("Keyboard disconnected")
            applied = False

        was_present = present
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
