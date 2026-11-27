import json

import g915x_rgb.gkey_actions as gkey_actions
from g915x_rgb.gkey_actions import (
    get_profile_switch_target,
    rename_profile_target,
)

def test_returns_target_for_switch_profile_action():
    actions = {
        0xB4: {
            "type": "switch_profile",
            "target": "Blue",
        }
    }

    assert get_profile_switch_target(actions, 0xB4) == "Blue"


def test_returns_none_when_action_is_missing():
    assert get_profile_switch_target({}, 0xB4) is None


def test_returns_none_for_unsupported_action():
    actions = {
        0xB4: {
            "type": "launch_application",
            "target": "Blue",
        }
    }

    assert get_profile_switch_target(actions, 0xB4) is None


def test_returns_none_for_invalid_target():
    actions = {
        0xB4: {
            "type": "switch_profile",
            "target": "   ",
        }
    }

    assert get_profile_switch_target(actions, 0xB4) is None


def test_returns_none_for_non_dict_action():
    assert get_profile_switch_target({0xB4: "Blue"}, 0xB4) is None


def test_strips_whitespace_from_profile_target():
    actions = {
        0xB4: {
            "type": "switch_profile",
            "target": "  Blue  ",
        }
    }

    assert get_profile_switch_target(actions, 0xB4) == "Blue"


def test_saves_actions_under_default_set(tmp_path, monkeypatch):
    path = tmp_path / "gkeys.json"
    monkeypatch.setattr(gkey_actions, "GKEYS_PATH", path)

    actions = {
        0xB4: {
            "type": "switch_profile",
            "target": "Blue",
        }
    }

    gkey_actions.save_gkey_actions(actions)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {
        "sets": {
            "Default": {
                "180": {
                    "type": "switch_profile",
                    "target": "Blue",
                }
            }
        }
    }


def test_saved_actions_load_correctly(tmp_path, monkeypatch):
    path = tmp_path / "gkeys.json"
    monkeypatch.setattr(gkey_actions, "GKEYS_PATH", path)

    actions = {
        0xB4: {
            "type": "switch_profile",
            "target": "Blue",
        }
    }

    gkey_actions.save_gkey_actions(actions)

    assert gkey_actions.load_gkey_actions() == actions


def test_rename_profile_target_updates_memory_and_saved_actions(
    tmp_path, monkeypatch
):
    path = tmp_path / "gkeys.json"
    monkeypatch.setattr(gkey_actions, "GKEYS_PATH", path)

    actions = {
        0xB4: {
            "type": "switch_profile",
            "target": "Old",
        }
    }

    assert rename_profile_target(actions, "Old", "New")
    assert actions[0xB4]["target"] == "New"

    gkey_actions.save_gkey_actions(actions)

    assert gkey_actions.load_gkey_actions() == {
        0xB4: {
            "type": "switch_profile",
            "target": "New",
        }
    }
