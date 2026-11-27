"""Shared G-key actions and persistence."""

from __future__ import annotations

import json

from .config import CONFIG_DIR, write_json

GKEYS_PATH = CONFIG_DIR / "gkeys.json"
GKEY_ADDRESSES = range(0xB4, 0xBD)


def _valid_action(action):
    if not isinstance(action, dict):
        return False

    if action.get("type") != "switch_profile":
        return False

    target = action.get("target")
    return isinstance(target, str) and bool(target.strip())


def load_gkey_actions() -> dict[int, dict]:
    """Load actions from the shared Default set."""
    try:
        data = json.loads(GKEYS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    sets = data.get("sets") if isinstance(data, dict) else None
    actions = sets.get("Default") if isinstance(sets, dict) else None
    if not isinstance(actions, dict):
        return {}

    result = {}
    for address, action in actions.items():
        try:
            address = int(address)
        except (TypeError, ValueError):
            continue

        if address in GKEY_ADDRESSES and _valid_action(action):
            result[address] = dict(action)

    return result


def save_gkey_actions(actions: dict[int, dict]) -> None:
    """Save shared actions in the Default set."""
    data = {
        "sets": {
            "Default": {
                str(address): dict(action)
                for address, action in actions.items()
                if address in GKEY_ADDRESSES and _valid_action(action)
            }
        }
    }
    write_json(GKEYS_PATH, data)


def rename_profile_target(actions: dict[int, dict], old: str, new: str) -> bool:
    """Update shared actions that point to a renamed profile."""
    changed = False

    for action in actions.values():
        if action.get("type") == "switch_profile" and action.get("target") == old:
            action["target"] = new
            changed = True

    return changed


def get_profile_switch_target(actions, address):
    action = actions.get(address)

    if not isinstance(action, dict):
        return None

    if action.get("type") != "switch_profile":
        return None

    target = action.get("target")

    if isinstance(target, str) and target.strip():
        return target.strip()

    return None
