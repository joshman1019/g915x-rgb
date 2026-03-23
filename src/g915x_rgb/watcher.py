"""Watch for keyboard (re)connection and apply the saved profile.

Polls for the G915 X hidraw device every few seconds. When the device
appears (or reappears after disconnection), applies the last-used profile.
This is safer than udev triggers which can interfere with device init.
"""

import sys
import time

from .backend import G915XBackend, KeyboardNotFoundError
from .config import get_last_profile
from .profile import Profile, create_default_profile, load_all_profiles

POLL_INTERVAL = 5  # seconds between checks


def find_profile(name: str | None) -> Profile:
    profiles = load_all_profiles()
    if name:
        for p in profiles:
            if p.name.lower() == name.lower():
                return p
    if profiles:
        return profiles[0]
    return create_default_profile()


def main():
    print("g915x-rgb watcher: monitoring for keyboard connection...")
    was_connected = False
    applied = False

    while True:
        try:
            kb = G915XBackend()
            kb.connect()
            is_connected = True
        except KeyboardNotFoundError:
            is_connected = False
            kb = None

        if is_connected and (not was_connected or not applied):
            # Keyboard just appeared or we haven't applied yet
            profile_name = get_last_profile()
            profile = find_profile(profile_name)
            print(f"Keyboard connected, applying profile: {profile.name}")
            try:
                colors = profile.get_all_key_colors()
                kb.set_all_keys(0, 0, 0)
                time.sleep(0.1)
                kb.apply_key_colors(colors)
                applied = True
                print("Profile applied successfully")
            except Exception as e:
                print(f"Error applying profile: {e}", file=sys.stderr)
                applied = False

        if is_connected and not was_connected:
            was_connected = True
        elif not is_connected and was_connected:
            was_connected = False
            applied = False
            print("Keyboard disconnected, waiting for reconnection...")

        if kb:
            kb.disconnect()

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
