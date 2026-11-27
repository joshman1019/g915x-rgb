"""State behind the interface: profiles, selection, undo and previews."""

from __future__ import annotations

import json
import logging
import time

from PySide6.QtCore import (
    Property, QAbstractListModel, QModelIndex, QObject, QProcess, Qt, QTimer, Signal, Slot,
)

from .animation import AnimationConfig, get_animation_choices
from .animation import ANIMATIONS, _lerp, _scale_frame
from .auto_switch import AutoSwitchRules, Rule
from .config import get_last_profile, get_options
from .daemon_proxy import DaemonProxy
from .keyboard_layout import (
    ALL_ADDRESSES, G915X_KEYS, KEY_BY_ADDRESS, KEY_GROUPS, LAYOUT_HEIGHT, LAYOUT_WIDTH,
)
from .gkey_actions import (
    load_gkey_actions,
    rename_profile_target,
    save_gkey_actions,
)
from .profile import (
    Profile, create_default_profile, duplicate_profile, load_all_profiles_with_errors,
    _parse_hex, _rgb_to_hex,
)
from .reactive import ReactiveOverlay
from .transitions import get_transition_choices

logger = logging.getLogger("g915x.editor")

GROUP_LABELS = {
    "keys": "Main keys", "fkeys": "F keys", "modifiers": "Modifiers", "arrows": "Arrows",
    "numeric": "Numpad", "functions": "Functions", "gkeys": "G keys",
    "multimedia": "Media", "indicators": "Indicators", "logo": "Logo",
}
TYPING = [("", "Off"), ("glow", "Glow"), ("ripple", "Ripple"),
          ("starburst", "Starburst"), ("heat", "Heat")]
MAX_UNDO = 50
MERGE_SECONDS = 0.8
BLACK = (0, 0, 0)


def _css(color) -> str:
    return "#" + _rgb_to_hex(color)


class KeyModel(QAbstractListModel):
    ROLES = {Qt.UserRole + 1 + i: n for i, n in enumerate(
        (b"name", b"label", b"keyX", b"keyY", b"keyW", b"keyH", b"address", b"lit", b"chosen"))}
    LIT, CHOSEN = Qt.UserRole + 8, Qt.UserRole + 9

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.colors: dict = {}
        self.selection: set[int] = set()

    def roleNames(self):
        return self.ROLES

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(G915X_KEYS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(G915X_KEYS):
            return None
        k = G915X_KEYS[index.row()]
        if role == self.LIT:
            return _css(self.colors.get(k.address, BLACK))
        if role == self.CHOSEN:
            return k.address in self.selection
        values = (k.name, k.label or k.name, k.x, k.y, k.w, k.h, k.address)
        i = role - Qt.UserRole - 1
        return values[i] if 0 <= i < len(values) else None

    def refresh(self, role: int) -> None:
        self.dataChanged.emit(self.index(0), self.index(len(G915X_KEYS) - 1), [role])


class Editor(QObject):
    profilesChanged = Signal()
    profileChanged = Signal()
    selectionChanged = Signal()
    statusChanged = Signal()
    optionsChanged = Signal()
    rulesChanged = Signal()
    loginChanged = Signal()
    playingChanged = Signal()
    message = Signal(str)
    windowPicked = Signal(str)

    def __init__(self, parent=None, daemon=None) -> None:
        super().__init__(parent)
        self._keys = KeyModel(self)
        self._profiles: list[Profile] = []
        self._index = 0
        self._undo: dict[int, list[dict]] = {}
        self._redo: dict[int, list[dict]] = {}
        self._saved: dict[int, dict] = {}
        self._last_edit = ("", 0.0)
        self._page = "colors"
        self._playing = True
        self._stream = None
        self._stream_key = None
        self._cfg = AnimationConfig()
        self._overlay = ReactiveOverlay("", BLACK)
        self._options = get_options()
        self._rules = AutoSwitchRules.load()
        self._status: dict = {}
        self._login = False

        self._push = QTimer(self, singleShot=True, interval=80)
        self._push.timeout.connect(self._send_preview)
        self._frames = QTimer(self, interval=1000 // 15)
        self._frames.timeout.connect(self._render)

        self._daemon = daemon if daemon is not None else DaemonProxy(self)
        self._daemon.status.connect(self._on_status)
        self._daemon.switched.connect(self._on_switched)
        self._daemon.windowPicked.connect(self.windowPicked)
        self._daemon.start()

        self._gkey_actions: dict[int, dict] = {}
        self._load_profiles()
        self._query_login()

    # ---------- loading ----------
    def _load_profiles(self) -> None:
        result = load_all_profiles_with_errors()
        self._profiles = result.profiles
        if not self._profiles:
            profile = create_default_profile()
            profile.save()
            self._profiles = [profile]
        self._gkey_actions = load_gkey_actions()
        for p in self._profiles:
            self._saved[id(p)] = p.to_dict()
        last = get_last_profile()
        self._index = next((i for i, p in enumerate(self._profiles) if p.name == last), 0)
        if result.errors:
            names = ", ".join(path.name for path, _ in result.errors)
            QTimer.singleShot(0, lambda: self.message.emit(f"Could not read: {names}"))
        self._refresh()

    def _save_gkey_actions(self) -> bool:
        try:
            save_gkey_actions(self._gkey_actions)
        except OSError as e:
            self.message.emit(f"Could not save G-key actions: {e}")
            return False

        self._daemon.reload_gkey_actions()
        return True

    @property
    def _p(self) -> Profile:
        return self._profiles[self._index]

    def _refresh(self) -> None:
        self.profilesChanged.emit()
        self.profileChanged.emit()
        self._render()


    # ---------- editing ----------
    def _begin(self, what: str) -> None:
        """Record an undo step; rapid edits of one control share a step."""
        key, now = f"{id(self._p)}:{what}", time.monotonic()
        merge = key == self._last_edit[0] and now - self._last_edit[1] < MERGE_SECONDS
        self._last_edit = (key, now)
        if not merge:
            stack = self._undo.setdefault(id(self._p), [])
            stack.append(self._p.to_dict())
            del stack[:-MAX_UNDO]
        self._redo.pop(id(self._p), None)

    def _edited(self) -> None:
        self._refresh()
        self._push.start()

    def _restore(self, data: dict) -> None:
        new = Profile.from_dict(data)
        p = self._p
        p.name, p.group_colors, p.key_colors = new.name, new.group_colors, new.key_colors
        p.startup, p.ambient, p.reactive = new.startup, new.ambient, new.reactive
        self._last_edit = ("", 0.0)
        self._edited()

    @Slot()
    def undo(self) -> None:
        stack = self._undo.get(id(self._p))
        if stack:
            self._redo.setdefault(id(self._p), []).append(self._p.to_dict())
            self._restore(stack.pop())

    @Slot()
    def redo(self) -> None:
        stack = self._redo.get(id(self._p))
        if stack:
            self._undo.setdefault(id(self._p), []).append(self._p.to_dict())
            self._restore(stack.pop())

    def _is_dirty(self, p: Profile) -> bool:
        return self._saved.get(id(p)) != p.to_dict()

    @Slot(result=bool)
    def save(self) -> bool:
        p = self._p
        old = (self._saved.get(id(p)) or {}).get("name")
        try:
            p.save()
            if old and old != p.name:
                old_gkey_actions = {
                    address: dict(action)
                    for address, action in self._gkey_actions.items()
                }
                if rename_profile_target(self._gkey_actions, old, p.name):
                    if not self._save_gkey_actions():
                        self._gkey_actions = old_gkey_actions
                        return False

            if old and old != p.name and (self._rules.fallback == old
                                          or any(r.profile == old for r in self._rules.rules)):
                for r in self._rules.rules:
                    if r.profile == old:
                        r.profile = p.name
                if self._rules.fallback == old:
                    self._rules.fallback = p.name
                self._store_rules()
        except OSError as e:
            self.message.emit(f"Could not save: {e.strerror or e}")
            return False

        self._saved[id(p)] = p.to_dict()
        self._push.stop()
        self._daemon.apply(p.name)
        self._refresh()
        return True

    @Slot(result=bool)
    def saveAll(self) -> bool:
        current = self._index
        ok = True
        for i, p in enumerate(self._profiles):
            if self._is_dirty(p):
                self._index = i
                ok = self.save() and ok
        self._index = current
        if not self._is_dirty(self._p):
            self._daemon.apply(self._p.name)
        self._refresh()
        return ok

    def _send_preview(self) -> None:
        self._daemon.preview(json.dumps(self._p.to_dict()))

    # ---------- profiles ----------
    @Slot(int)
    def selectProfile(self, index: int) -> None:
        if 0 <= index < len(self._profiles) and index != self._index:
            self._index = index
            self._push.stop()
            if self._is_dirty(self._p):
                self._send_preview()
            else:
                self._daemon.apply(self._p.name, "fade")
            self._refresh()

    def _free_name(self, name: str, ignore: Profile | None = None) -> str:
        used = {p.name.lower() for p in self._profiles if p is not ignore}
        candidate, n = name, 2
        while candidate.lower() in used:
            candidate, n = f"{name} {n}", n + 1
        return candidate

    @Slot()
    def addProfile(self) -> None:
        self._profiles.append(duplicate_profile(self._p, self._free_name("New profile")))
        self._index = len(self._profiles) - 1
        self._edited()

    @Slot(str)
    def renameProfile(self, name: str) -> None:
        name = name.strip()
        if name and name != self._p.name:
            self._begin("name")
            self._p.name = self._free_name(name, self._p)
            self._edited()

    @Slot()
    def deleteProfile(self) -> None:
        if len(self._profiles) < 2:
            return
        p = self._p
        try:
            p.delete()
        except OSError as e:
            self.message.emit(f"Could not delete: {e.strerror or e}")
            return
        for store in (self._undo, self._redo, self._saved):
            store.pop(id(p), None)
        self._profiles.remove(p)
        self._index = min(self._index, len(self._profiles) - 1)
        if not self._is_dirty(self._p):
            self._daemon.apply(self._p.name)
        self._refresh()

    # ---------- selection and colors ----------
    def _select(self, addresses: set[int]) -> None:
        self._keys.selection = addresses
        self._keys.refresh(KeyModel.CHOSEN)
        self.selectionChanged.emit()

    @Slot(int)
    def keyClicked(self, address: int) -> None:
        if self._page == "typing":
            self._overlay.trigger(address)
        elif self._page == "colors":
            self._select(self._keys.selection ^ {address})

    @Slot(float, float, float, float, bool)
    def selectArea(self, x1, y1, x2, y2, add) -> None:
        if self._page != "colors":
            return
        inside = {k.address for k in G915X_KEYS
                  if x1 <= k.x + k.w / 2 <= x2 and y1 <= k.y + k.h / 2 <= y2}
        self._select(self._keys.selection | inside if add else inside)

    @Slot(str)
    def selectGroup(self, group: str) -> None:
        self._select({k.address for k in KEY_GROUPS.get(group, [])})

    @Slot()
    def selectAll(self) -> None:
        self._select(set(ALL_ADDRESSES))

    @Slot()
    def clearSelection(self) -> None:
        self._select(set())

    @Slot(str)
    def fill(self, color: str) -> None:
        if not self._keys.selection:
            return
        rgb = _parse_hex(color)
        self._begin("fill")
        left = set(self._keys.selection)
        for group, keys in KEY_GROUPS.items():
            members = {k.address for k in keys}
            if members <= left:                 # whole group: set the group itself
                self._p.group_colors[group] = rgb
                for a in members:
                    self._p.key_colors.pop(a, None)
                left -= members
        for a in left:
            self._p.key_colors[a] = rgb
        self._edited()

    @Slot(str, str)
    def blend(self, first: str, second: str) -> None:
        chosen = [KEY_BY_ADDRESS[a] for a in self._keys.selection]
        if not chosen:
            return
        self._begin("blend")
        c1, c2 = _parse_hex(first), _parse_hex(second)
        xs = [k.x + k.w / 2 for k in chosen]
        low, span = min(xs), max(max(xs) - min(xs), 0.001)
        for k, x in zip(chosen, xs):
            self._p.key_colors[k.address] = _lerp(c1, c2, (x - low) / span)
        self._edited()

    @Slot()
    def resetToGroup(self) -> None:
        if any(a in self._p.key_colors for a in self._keys.selection):
            self._begin("reset")
            for a in self._keys.selection:
                self._p.key_colors.pop(a, None)
            self._edited()

    # ---------- effects ----------
    @Slot(str, str, "QVariant")
    def setEffect(self, slot: str, field: str, value) -> None:
        target = {"ambient": self._p.ambient, "startup": self._p.startup,
                  "reactive": self._p.reactive}.get(slot)
        if target is None or not hasattr(target, field):
            return
        if field in ("primary", "secondary", "color"):
            value = _parse_hex(value)
        elif field in ("speed", "intensity"):
            value = max(0.05, min(3.0, float(value)))
        else:
            value = str(value)
        if getattr(target, field) == value:
            return
        self._begin(f"{slot}.{field}")
        setattr(target, field, value)
        self._edited()


    @Slot(int, str, str)
    def setGKeyAction(self, address: int, action_type: str, target: str) -> None:
        if address not in range(0xB4, 0xBD):
            return

        if action_type == "":
            action = None
        elif action_type == "switch_profile":
            target = target.strip()
            if not target or target not in {p.name for p in self._profiles}:
                return
            action = {"type": action_type, "target": target}
        else:
            return

        if self._gkey_actions.get(address) == action:
            return

        previous = self._gkey_actions.get(address)

        if action is None:
            self._gkey_actions.pop(address, None)
        else:
            self._gkey_actions[address] = action

        if not self._save_gkey_actions():
            if previous is None:
                self._gkey_actions.pop(address, None)
            else:
                self._gkey_actions[address] = previous
            return

        self._refresh()


    @Slot(str)
    def setPage(self, page: str) -> None:
        self._page = page
        self._render()

    @Slot(bool)
    def setPlaying(self, playing: bool) -> None:
        self._playing = playing
        self.playingChanged.emit()
        self._render()

    def _render(self) -> None:
        """Update the on-screen keyboard, animating only where it shows."""
        p = self._p
        amb = p.ambient
        animate = self._page == "effects" and amb.name in ANIMATIONS
        frame = p.get_all_key_colors()
        if animate:
            self._cfg.primary, self._cfg.secondary = amb.primary, amb.secondary
            self._cfg.speed, self._cfg.intensity = amb.speed, amb.intensity
            if self._stream_key != amb.name:
                self._stream = ANIMATIONS[amb.name][1](self._cfg)
                self._stream_key = amb.name
            frame = _scale_frame(next(self._stream)[0], amb.intensity)
        else:
            self._stream = self._stream_key = None
        typing = self._page == "typing" and bool(p.reactive.effect)
        if typing:
            o = self._overlay
            o.effect, o.color, o.intensity = p.reactive.effect, p.reactive.color, p.reactive.intensity
            for a, (color, alpha) in o(time.monotonic()).items():
                frame[a] = _lerp(frame.get(a, BLACK), color, alpha)
        if frame != self._keys.colors:
            self._keys.colors = frame
            self._keys.refresh(KeyModel.LIT)
        run = (animate and self._playing) or typing
        if run != self._frames.isActive():
            self._frames.start() if run else self._frames.stop()

    # ---------- service ----------
    def _on_status(self, status: dict) -> None:
        self._status = status
        self.statusChanged.emit()

    def _on_switched(self, name: str, reason: str) -> None:
        # Follow automatic switches, but never away from unsaved work.
        if (reason.startswith("window:") or reason == "gkey") and not self._is_dirty(self._p):
            for i, p in enumerate(self._profiles):
                if p.name == name and i != self._index:
                    self._index = i
                    self._refresh()
                    break

    @Slot(str, "QVariant")
    def setOption(self, name: str, value) -> None:
        if isinstance(self._options.get(name), bool):
            value = bool(value)
        elif isinstance(self._options.get(name), int):
            value = int(value)
        self._options[name] = value
        self._daemon.set_option(name, json.dumps(value))
        self.optionsChanged.emit()

    # ---------- rules ----------
    def _store_rules(self) -> None:
        try:
            self._rules.save()
        except OSError as e:
            self.message.emit(f"Could not save rules: {e.strerror or e}")
        self._daemon.reload_rules()
        self.rulesChanged.emit()

    @Slot(bool)
    def setRulesEnabled(self, enabled: bool) -> None:
        self._rules.enabled = enabled
        self._store_rules()

    @Slot(str, str)
    def addRule(self, pattern: str, profile: str) -> None:
        if pattern.strip() and profile:
            self._rules.rules.append(Rule(profile=profile, class_regex=pattern.strip()))
            self._store_rules()

    @Slot(str)
    def setFallback(self, profile: str) -> None:
        """The profile for windows no rule matches; empty keeps the chosen one."""
        self._rules.fallback = profile or None
        self._store_rules()

    @Slot(int, str, str)
    def updateRule(self, index: int, field: str, value: str) -> None:
        if 0 <= index < len(self._rules.rules) and field in ("profile", "transition", "class_regex"):
            if field == "class_regex" and not value.strip():
                return
            setattr(self._rules.rules[index], field, value)
            self._store_rules()

    @Slot(int)
    def removeRule(self, index: int) -> None:
        if 0 <= index < len(self._rules.rules):
            del self._rules.rules[index]
            self._store_rules()

    @Slot()
    def pickWindow(self) -> None:
        self._daemon.pick_window()

    # ---------- login service ----------
    def _systemctl(self, args: list[str], done) -> None:
        proc = QProcess(self)
        proc.finished.connect(lambda code, _status: (done(code, proc), proc.deleteLater()))
        proc.errorOccurred.connect(lambda _e: proc.deleteLater())
        proc.start("systemctl", ["--user", *args])

    def _query_login(self) -> None:
        def done(code, _proc) -> None:
            self._login = code == 0
            self.loginChanged.emit()
        self._systemctl(["is-enabled", "--quiet", "g915x-rgb.service"], done)

    @Slot(bool)
    def setLogin(self, enabled: bool) -> None:
        def done(code, proc) -> None:
            if code:
                error = bytes(proc.readAllStandardError()).decode(errors="replace").strip()
                self.message.emit(error or "Could not change the login service")
            self._query_login()
        self._systemctl(["enable" if enabled else "disable", "g915x-rgb.service"], done)

    def shutdown(self) -> None:
        self._push.stop()
        self._frames.stop()
        self._daemon.stop_preview()

    # ---------- properties ----------
    def _get_profiles(self):
        out = []
        for p in self._profiles:
            colors = p.get_all_key_colors()
            strip = [_css(colors[a]) for a in ALL_ADDRESSES[::12]]
            out.append({"name": p.name, "strip": strip, "dirty": self._is_dirty(p)})
        return out

    def _get_profile(self):
        def anim(a):
            return {"name": a.name, "primary": _css(a.primary), "secondary": _css(a.secondary),
                    "speed": a.speed, "intensity": a.intensity}
        p = self._p
        return {
            "name": p.name, "index": self._index, "dirty": self._is_dirty(p),
            "canUndo": bool(self._undo.get(id(p))),
            "canRedo": bool(self._redo.get(id(p))),
            "ambient": anim(p.ambient), "startup": anim(p.startup),
            "reactive": {"effect": p.reactive.effect, "color": _css(p.reactive.color),
                         "intensity": p.reactive.intensity},

            "gkeys": [
                {
                    "address": address,
                    "name": f"G{address - 0xB3}",
                    "type": self._gkey_actions.get(address, {}).get("type", ""),
                    "target": self._gkey_actions.get(address, {}).get("target", ""),
                }
                for address in range(0xB4, 0xBD)
            ],

            "groups": [{"id": g, "label": label, "count": len(KEY_GROUPS[g]),
                        "color": _css(p.group_colors.get(g, BLACK))}
                       for g, label in GROUP_LABELS.items()],
        }

    def _get_selection(self):
        chosen = self._keys.selection
        first = next((a for a in ALL_ADDRESSES if a in chosen), None)
        color = self._p.get_effective_color(first) if first is not None else (255, 255, 255)
        return {"count": len(chosen), "color": _css(color)}

    def _get_rules(self):
        return {"enabled": self._rules.enabled, "fallback": self._rules.fallback or "", "items": [
            {"pattern": r.class_regex or "", "profile": r.profile,
             "transition": r.transition or self._rules.transition}
            for r in self._rules.rules]}

    keys = Property(QObject, lambda self: self._keys, constant=True)
    layoutWidth = Property(float, lambda self: LAYOUT_WIDTH, constant=True)
    layoutHeight = Property(float, lambda self: LAYOUT_HEIGHT, constant=True)
    effects = Property("QVariantList", lambda self: [
        {"id": n, "label": n.capitalize(), "detail": d.split("—")[-1].strip()}
        for n, d in get_animation_choices()], constant=True)
    typingEffects = Property("QVariantList", lambda self: [
        {"id": i, "label": label} for i, label in TYPING], constant=True)
    transitions = Property("QVariantList", lambda self: [
        {"id": n, "label": n.replace("_", " ").capitalize()}
        for n, _ in get_transition_choices()], constant=True)
    profiles = Property("QVariantList", _get_profiles, notify=profilesChanged)
    profile = Property("QVariantMap", _get_profile, notify=profileChanged)
    selection = Property("QVariantMap", _get_selection, notify=selectionChanged)
    status = Property("QVariantMap", lambda self: self._status, notify=statusChanged)
    options = Property("QVariantMap", lambda self: dict(self._options), notify=optionsChanged)
    rules = Property("QVariantMap", _get_rules, notify=rulesChanged)
    login = Property(bool, lambda self: self._login, notify=loginChanged)
    playing = Property(bool, lambda self: self._playing, notify=playingChanged)
    anyDirty = Property(bool, lambda self: any(map(self._is_dirty, self._profiles)),
                        notify=profilesChanged)
