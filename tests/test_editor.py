"""Editing behavior behind the interface."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from g915x_rgb.keyboard_layout import KEY_GROUPS  # noqa: E402
from g915x_rgb.profile import Profile, load_all_profiles  # noqa: E402


class FakeDaemon(QObject):
    status, switched, windowPicked = Signal(dict), Signal(str, str), Signal(str)

    def __init__(self):
        super().__init__()
        self.calls = []

    def start(self):
        pass

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *args: self.calls.append((name, *args))


@pytest.fixture
def editor(home, monkeypatch):
    QApplication.instance() or QApplication([])
    import g915x_rgb.editor as module
    monkeypatch.setattr(module.Editor, "_query_login", lambda self: None)
    Profile(name="One", group_colors={g: (255, 0, 0) for g in KEY_GROUPS}).save()
    Profile(name="Two", group_colors={"keys": (0, 255, 0)}).save()
    e = module.Editor(daemon=FakeDaemon())
    yield e
    e.shutdown()


def test_selecting_changes_no_colors(editor):
    before = editor._p.to_dict()
    editor.selectAll()
    editor.keyClicked(0x10)
    editor.selectGroup("logo")
    assert editor._p.to_dict() == before and not editor.anyDirty


def test_switching_profiles_leaks_nothing(editor):
    editor.selectProfile(1)
    editor.selectProfile(0)
    assert not editor.anyDirty
    assert editor._profiles[1].group_colors == {"keys": (0, 255, 0)}


def test_fill_undo_redo(editor):
    editor.selectGroup("logo")
    editor.fill("#010203")
    assert editor._p.group_colors["logo"] == (1, 2, 3)
    editor.undo()
    assert editor._p.group_colors["logo"] == (255, 0, 0)
    editor.redo()
    assert editor._p.group_colors["logo"] == (1, 2, 3)


def test_gkey_action_saves_without_undo(editor):
    action = {"type": "switch_profile", "target": "Two"}

    editor.setGKeyAction(180, "switch_profile", "Two")

    assert editor._gkey_actions[180] == action
    assert not editor.canUndo
    assert not editor.canRedo

    editor.undo()
    assert editor._gkey_actions[180] == action


def test_blend_spans_the_selection_and_resets(editor):
    editor.selectGroup("fkeys")
    editor.blend("#000000", "#ffffff")
    keys = sorted(KEY_GROUPS["fkeys"], key=lambda k: k.x)
    assert editor._p.get_effective_color(keys[0].address) == (0, 0, 0)
    assert editor._p.get_effective_color(keys[-1].address) == (255, 255, 255)
    editor.resetToGroup()
    assert editor._p.get_effective_color(keys[0].address) == (255, 0, 0)


def test_rename_save_and_delete(editor):
    editor.addRule("konsole", "One")
    editor.setFallback("One")
    editor.renameProfile("Renamed")
    assert editor.save()
    assert editor._rules.rules[0].profile == "Renamed"
    assert editor._rules.fallback == "Renamed"
    assert editor.rules["fallback"] == "Renamed"
    assert {p.name for p in load_all_profiles()} == {"Renamed", "Two"}
    editor.deleteProfile()
    assert [p.name for p in load_all_profiles()] == ["Two"]
    editor.deleteProfile()
    assert [p.name for p in load_all_profiles()] == ["Two"]


def test_new_profiles_get_free_names(editor):
    editor.addProfile()
    editor.addProfile()
    assert [p.name for p in editor._profiles[2:]] == ["New profile", "New profile 2"]


def test_save_all(editor):
    editor.setEffect("ambient", "name", "fire")
    editor.selectProfile(1)
    editor.setEffect("ambient", "speed", 2.0)
    assert editor.anyDirty and editor.saveAll() and not editor.anyDirty


def test_automatic_switch_never_leaves_unsaved_work(editor):
    editor._on_switched("Two", "window:steam")
    assert editor.profile["name"] == "Two"
    editor.setEffect("ambient", "name", "fire")
    editor._on_switched("One", "window:steam")
    assert editor.profile["name"] == "Two"
