"""Renderer, profile storage and daemon behavior, with a fake keyboard."""

from __future__ import annotations

import json
import time

import pytest

from g915x_rgb import config
from g915x_rgb.keyboard_layout import ALL_ADDRESSES, KEY_GROUPS
from g915x_rgb.profile import Profile, load_all_profiles
from g915x_rgb.renderer import Renderer

pytest.importorskip("dbus")
from g915x_rgb import daemon  # noqa: E402


class FakeKeyboard:
    def __init__(self):
        self.is_connected = False
        self.lit = {}
        self.sent = 0
        self.fail = False

    def connect(self):
        self.is_connected = True

    def disconnect(self):
        self.is_connected = False

    def get_battery(self):
        return (10, False)

    def apply_key_colors(self, colors):
        if self.fail:
            raise OSError("gone")
        self.sent += len(colors)
        self.lit.update(colors)


def wait(condition, seconds=3.0):
    end = time.monotonic() + seconds
    while not condition() and time.monotonic() < end:
        time.sleep(0.02)
    return condition()


def solid(name, color, **kw):
    return Profile(name=name, group_colors={g: color for g in KEY_GROUPS}, **kw)


def test_failed_frame_is_sent_again():
    kb = FakeKeyboard()
    r = Renderer(kb)
    kb.fail = True
    r._cancel.set()
    r._diff_send({1: (9, 9, 9)})
    kb.fail = False
    r._diff_send({1: (9, 9, 9)})
    assert kb.lit == {1: (9, 9, 9)}


def test_restart_resends_everything():
    kb = FakeKeyboard()
    r = Renderer(kb)
    r.set_base({1: (9, 9, 9)})
    r.start()
    assert wait(lambda: kb.lit)
    r.stop()
    kb.lit = {}
    r.start()
    assert wait(lambda: kb.lit)
    r.stop()


def test_names_that_look_alike_do_not_overwrite(home):
    a, b = Profile(name="A b"), Profile(name="A/b")
    assert a.save() != b.save()
    assert {p.name for p in load_all_profiles()} == {"A b", "A/b"}


def test_delete_and_rename_leave_no_files_behind(home):
    p = Profile(name="One")
    p.save()
    p.name = "Two"
    p.save()
    assert [q.name for q in load_all_profiles()] == ["Two"]
    p.delete()
    assert load_all_profiles() == []


def test_unset_groups_are_black():
    colors = Profile(name="x", group_colors={"keys": (1, 1, 1)}).get_all_key_colors()
    assert set(colors) == set(ALL_ADDRESSES)
    assert colors[KEY_GROUPS["logo"][0].address] == (0, 0, 0)


def test_damaged_profile_is_skipped(home):
    Profile(name="Good").save()
    (home / "profiles" / "bad.json").write_text('{"groups": {"keys": "zzz"}}')
    (home / "profiles" / "list.json").write_text("[]")
    assert [p.name for p in load_all_profiles()] == ["Good"]


def test_options_reject_unknown_names_and_types(home):
    assert not config.set_option("nope", 1)
    assert not config.set_option("idle_minutes", True)
    assert config.set_option("idle_minutes", 5)
    config.set_last_profile("x")
    assert config.get_options()["idle_minutes"] == 5


@pytest.fixture
def ctl(home):
    solid("Red", (255, 0, 0)).save()
    solid("Blue", (0, 0, 255)).save()
    kb = FakeKeyboard()
    c = daemon.Controller(kb, defer=lambda fn, *args: fn(*args))
    c.reload_profiles()
    config.set_last_profile("Red")
    c.connect()
    yield c, kb
    c.disconnect()


def all_lit(kb, color):
    return wait(lambda: len(kb.lit) == len(ALL_ADDRESSES) and set(kb.lit.values()) == {color})


def test_last_profile_is_applied_on_connect(ctl):
    assert all_lit(ctl[1], (255, 0, 0))


def test_reconnect_restores_lighting(ctl):
    c, kb = ctl
    assert all_lit(kb, (255, 0, 0))
    c.disconnect()
    kb.lit = {}
    c.connect()
    assert all_lit(kb, (255, 0, 0))


def test_preview_is_temporary(ctl):
    c, kb = ctl
    assert c.preview(json.dumps(solid("tmp", (1, 2, 3)).to_dict()))
    assert all_lit(kb, (1, 2, 3))
    assert config.get_last_profile() == "Red"
    c.stop_preview()
    assert all_lit(kb, (255, 0, 0))
    assert not c.preview("not json")


def test_transition_ends_on_the_new_profile(ctl):
    c, kb = ctl
    assert c.set_profile("Blue", "fade")
    assert all_lit(kb, (0, 0, 255))


def test_gkey_action_persists_across_profile_switches(ctl):
    c, _ = ctl
    g1 = KEY_GROUPS["gkeys"][0].address

    c._gkey_actions[g1] = {
        "type": "switch_profile",
        "target": "Blue",
    }

    c._key_pressed(g1)
    assert c.status.current_profile == "Blue"

    c.set_profile("Red")
    assert c.status.current_profile == "Red"

    c._key_pressed(g1)
    assert c.status.current_profile == "Blue"


def test_gkey_action_does_not_switch_profile_during_preview(ctl):
    c, _ = ctl
    g1 = KEY_GROUPS["gkeys"][0].address

    c._gkey_actions[g1] = {
        "type": "switch_profile",
        "target": "Blue",
    }

    c.preview(json.dumps(solid("tmp", (1, 2, 3)).to_dict()))
    c._key_pressed(g1)

    assert c.status.current_profile == "Red"

    c.stop_preview()
    c._key_pressed(g1)

    assert c.status.current_profile == "Blue"


def test_replaced_startup_effect_does_not_return(ctl):
    c, kb = ctl
    animated = solid("a", (1, 1, 1))
    animated.ambient.name = animated.startup.name = "plasma"
    c._show(animated, startup=True)
    c._show(solid("b", (2, 2, 2)))
    assert all_lit(kb, (2, 2, 2))
    assert c._renderer.ambient_name() == ""


def test_startup_effect_gives_way_to_the_background(ctl, monkeypatch):
    c, _ = ctl
    monkeypatch.setattr(daemon, "STARTUP_SECONDS", 0.2)
    p = solid("a", (1, 1, 1))
    p.startup.name, p.ambient.name = "plasma", "fire"
    c._show(p, startup=True)
    assert wait(lambda: c._renderer.ambient_name() == "fire")


def test_tiny_changes_are_skipped_only_while_moving():
    kb = FakeKeyboard()
    r = Renderer(kb)
    r._diff_send({1: (100, 0, 0), 2: (3, 0, 0)})
    r._moving = True
    r._diff_send({1: (102, 0, 0), 2: (0, 0, 0)})
    assert kb.lit == {1: (100, 0, 0), 2: (0, 0, 0)}
    r._moving = False
    r._diff_send({1: (102, 0, 0), 2: (0, 0, 0)})
    assert kb.lit[1] == (102, 0, 0)


def test_lock_turns_off_and_unlock_restores(ctl):
    c, kb = ctl
    assert all_lit(kb, (255, 0, 0))
    c.set_locked(True)
    assert all_lit(kb, (0, 0, 0))
    c.set_locked(False)
    assert all_lit(kb, (255, 0, 0))


def test_idle_dims(ctl):
    c, kb = ctl
    c._set_idle(True)
    assert all_lit(kb, (38, 0, 0))


def test_low_battery_marks_g_keys(ctl):
    c, kb = ctl
    c.set_profile("Blue")
    c.set_option("battery_gkeys", True)
    g1 = KEY_GROUPS["gkeys"][0].address
    assert wait(lambda: kb.lit.get(g1) == (255, 0, 0))


def test_rules_switch_profiles_but_not_during_a_preview(ctl):
    c, _ = ctl
    c.rules = daemon.AutoSwitchRules.from_dict(
        {"enabled": True, "rules": [{"profile": "Blue", "class_regex": "^steam$"}]})
    c.preview(json.dumps(solid("tmp", (1, 2, 3)).to_dict()))
    c.window_changed("steam", "")
    assert c.status.current_profile == "Red"
    c.stop_preview()
    c.window_changed("steam", "")
    assert c.status.current_profile == "Blue"


def test_rules_return_to_the_chosen_profile(ctl):
    c, _ = ctl
    c.rules = daemon.AutoSwitchRules.from_dict(
        {"enabled": True, "rules": [{"profile": "Blue", "class_regex": "konsole"}]})
    c.window_changed("org.kde.konsole", "shell")
    assert c.status.current_profile == "Blue"
    assert config.get_last_profile() == "Red"
    c.window_changed("firefox", "page")
    assert c.status.current_profile == "Red"


def test_rule_checked_again_after_a_preview(ctl):
    c, _ = ctl
    c.rules = daemon.AutoSwitchRules.from_dict(
        {"enabled": True, "rules": [{"profile": "Blue", "class_regex": "konsole"}]})
    c.preview(json.dumps(solid("tmp", (1, 2, 3)).to_dict()))
    c.window_changed("org.kde.konsole", "shell")
    assert c.status.current_profile == "Red"
    c.stop_preview()
    assert c.status.current_profile == "Blue"


@pytest.mark.parametrize("pattern", ["*Konsole*", "konsole", "^org\\.kde\\.konsole$", "org.kde.*"])
def test_rule_patterns(pattern):
    rule = daemon.AutoSwitchRules.from_dict(
        {"rules": [{"profile": "x", "class_regex": pattern}]}).rules[0]
    assert rule.matches("org.kde.konsole", "")
    assert not rule.matches("firefox", "")


def test_fallback_covers_unmatched_windows(ctl):
    c, _ = ctl
    c.rules = daemon.AutoSwitchRules.from_dict(
        {"enabled": True, "fallback": "Red",
         "rules": [{"profile": "Blue", "class_regex": "konsole"}]})
    c.set_profile("Blue")          # chosen in the editor, e.g. to edit it
    c.window_changed("firefox", "page")
    assert c.status.current_profile == "Red"
    c.window_changed("org.kde.konsole", "shell")
    assert c.status.current_profile == "Blue"


def test_missing_fallback_keeps_the_chosen_profile(ctl):
    c, _ = ctl
    c.rules = daemon.AutoSwitchRules.from_dict(
        {"enabled": True, "fallback": "Gone",
         "rules": [{"profile": "Blue", "class_regex": "konsole"}]})
    c.window_changed("org.kde.konsole", "shell")
    c.window_changed("firefox", "page")
    assert c.status.current_profile == "Red"


def test_catch_all_rule_becomes_the_fallback():
    old = {"rules": [{"profile": "Blue", "class_regex": "konsole"},
                     {"profile": "Red", "class_regex": ".*"}]}
    rules = daemon.AutoSwitchRules.from_dict(old)
    assert rules.fallback == "Red" and len(rules.rules) == 1
    again = daemon.AutoSwitchRules.from_dict(rules.to_dict())
    assert again.fallback == "Red" and len(again.rules) == 1


def test_own_windows_do_not_switch(ctl):
    c, _ = ctl
    c.rules = daemon.AutoSwitchRules.from_dict(
        {"enabled": True, "fallback": "Red",
         "rules": [{"profile": "Blue", "class_regex": "konsole"}]})
    c.window_changed(daemon.APP_ID, "Red — G915 X Lighting")
    c.set_profile("Blue")          # picked in the editor
    c.window_changed(daemon.APP_ID, "Choose a color")
    assert c.status.current_profile == "Blue"
    c.window_changed("firefox", "page")
    assert c.status.current_profile == "Red"
