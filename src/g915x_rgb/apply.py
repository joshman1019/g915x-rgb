"""CLI tool to apply the last-used profile to the keyboard.

Used by the systemd service on login/resume.
Usage: python -m g915x_rgb.apply [profile_name]
"""

import sys
import time

from .animation import play_animation
from .backend import G915XBackend, KeyboardNotFoundError
from .config import get_last_profile
from .profile import Profile, create_default_profile, load_all_profiles


def apply_profile(profile: Profile, retries: int = 3) -> bool:
    """Apply a profile to the keyboard with retry logic."""
    for attempt in range(retries):
        try:
            kb = G915XBackend()
            kb.connect()
            play_animation(profile.startup_animation, kb, profile=profile)
            colors = profile.get_all_key_colors()
            kb.set_all_keys(0, 0, 0)
            time.sleep(0.1)
            kb.apply_key_colors(colors)
            kb.disconnect()
            return True
        except KeyboardNotFoundError:
            if attempt < retries - 1:
                time.sleep(2)
            continue
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(1)
            continue
    return False


def main():
    # Determine which profile to apply
    if len(sys.argv) > 1:
        target_name = sys.argv[1]
    else:
        target_name = get_last_profile()

    if not target_name:
        target_name = "Default"

    # Find the profile
    profiles = load_all_profiles()
    profile = None
    for p in profiles:
        if p.name.lower() == target_name.lower():
            profile = p
            break

    if profile is None:
        profile = create_default_profile()
        print(f"Profile '{target_name}' not found, using default")

    print(f"Applying profile: {profile.name}")
    if apply_profile(profile):
        print("Done!")
    else:
        print("Failed to apply profile (keyboard not found)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
