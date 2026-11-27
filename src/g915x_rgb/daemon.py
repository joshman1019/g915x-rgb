"""Background service that owns the keyboard.

Everything here runs on the GLib main thread except the renderer
and the key reader. Callbacks from those threads are
passed back through ``GLib.idle_add``.

D-Bus: ``org.g915xrgb.Controller`` at ``/org/g915xrgb/Controller``. Structured
values travel as JSON strings, which every client can decode the same way.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
from dataclasses import asdict, dataclass

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

from . import APP_ID
from .animation import ANIMATIONS, AnimationConfig
from .auto_switch import AutoSwitchRules, KWinSource, detect_compositor, find_kwin_script
from .backend import G915XBackend, KeyboardNotFoundError, device_present
from .config import get_last_profile, get_options, set_last_profile, set_option
from .idle import IdleWatcher
from .keyboard_layout import ALL_ADDRESSES, KEY_GROUPS
from .gkey_actions import get_profile_switch_target, load_gkey_actions
from .logging_setup import configure as configure_logging
from .profile import (
    AnimationProfile,
    Profile,
    create_default_profile,
    load_all_profiles_with_errors,
)
from .reactive import HAVE_EVDEV, KeyEventReader, ReactiveOverlay, find_keyboard_event_devices
from .renderer import Renderer
from .transitions import TRANSITIONS, TransitionConfig

BUS_NAME = "org.g915xrgb.Controller"
OBJECT_PATH = "/org/g915xrgb/Controller"

POLL_SECONDS = 2
SETTLE_SECONDS = 2
BATTERY_SECONDS = 60
LOW_BATTERY = 15
IDLE_BRIGHTNESS = 0.15
STARTUP_SECONDS = 3.0
TRANSITION_SECONDS = 0.6

BLACK_FRAME = dict.fromkeys(ALL_ADDRESSES, (0, 0, 0))
GKEYS = [k.address for k in KEY_GROUPS["gkeys"]]

logger = logging.getLogger("g915x.daemon")


def _animation_config(p: AnimationProfile) -> AnimationConfig:
    return AnimationConfig(primary=p.primary, secondary=p.secondary,
                           speed=p.speed, intensity=p.intensity)


@dataclass
class Status:
    connected: bool = False
    access_denied: bool = False
    current_profile: str = ""
    battery_percent: int = -1
    battery_charging: bool = False
    typing_available: bool = True
    idle_available: bool = True
    auto_switch: bool = False


class Controller:
    """Profile, device and effect logic, independent of D-Bus."""

    def __init__(self, kb=None, defer=GLib.idle_add) -> None:
        self._kb = kb if kb is not None else G915XBackend()
        self._defer = defer
        self._renderer = Renderer(self._kb)
        self._renderer.set_filter(self._post_process)
        self.status = Status()
        self.options = get_options()
        self.rules = AutoSwitchRules.load()
        self.on_status = lambda status: None
        self.on_switched = lambda name, reason: None

        self._profiles: list[Profile] = []
        self._gkey_actions: dict[int, dict] = {}
        self._current: Profile | None = None    # last applied, saved profile
        self._shown: Profile | None = None      # what is on the keyboard now
        self._generation = 0
        self._previewing = False
        self._settling = False
        self._locked = False
        self._idle = False
        self._reactive: ReactiveOverlay | None = None
        self._reader: KeyEventReader | None = None
        self._window_source: KWinSource | None = None
        self._last_window = ("", "")
        self._chosen: str | None = None         # picked by the person, not a rule
        self._idle_watch: tuple[IdleWatcher, int] | None = None

    # ---------- profiles ----------
    def reload_profiles(self) -> list[dict]:
        result = load_all_profiles_with_errors()
        self._profiles = result.profiles
        self._gkey_actions = load_gkey_actions()

        for path, msg in result.errors:
            logger.warning("could not load profile %s: %s", path, msg)

        self._configure_reactive()
        return [{"path": str(p), "error": m} for p, m in result.errors]

    def reload_gkey_actions(self) -> None:
        """Reload shared G-key actions from disk."""
        self._gkey_actions = load_gkey_actions()
        self._configure_reactive()

    def find_profile(self, name: str) -> Profile | None:
        for p in self._profiles:
            if p.name == name:
                return p
        return next((p for p in self._profiles if p.name.lower() == name.lower()), None)

    def set_profile(self, name: str, transition: str = "", reason: str = "manual") -> bool:
        profile = self.find_profile(name)
        if profile is None:
            logger.warning("profile %r not found", name)
            return False
        self._previewing = False
        self._current = profile
        self.status.current_profile = profile.name
        if not reason.startswith("window:"):
            # Rules switch away from this profile and back to it again.
            self._chosen = profile.name
            try:
                set_last_profile(profile.name)
            except OSError as e:
                logger.warning("could not remember the profile: %s", e)
        self._show(profile, transition=transition,
                   startup=reason in ("boot", "reconnect"))
        self.on_switched(profile.name, reason)
        self.emit_status()
        return True

    def preview(self, payload: str) -> bool:
        """Show an unsaved profile without making it current."""
        try:
            profile = Profile.from_dict(json.loads(payload))
        except (KeyError, ValueError, TypeError, AttributeError) as e:
            logger.warning("bad preview: %s", e)
            return False
        self._previewing = True
        self._show(profile)
        return True

    def stop_preview(self) -> None:
        if self._previewing:
            self._previewing = False
            if self._current is not None:
                self._show(self._current)
            self._apply_rules()

    def _show(self, profile: Profile, *, transition: str = "", startup: bool = False) -> None:
        self._generation += 1
        generation = self._generation
        previous, self._shown = self._shown, profile
        frame = profile.get_all_key_colors()
        ambient = profile.ambient if profile.ambient.name in ANIMATIONS else None

        def start_ambient() -> bool:
            # A newer profile may have been shown while this one played in.
            if generation == self._generation and ambient is not None:
                self._renderer.start_ambient(ambient.name, _animation_config(ambient))
            return False

        self._configure_reactive()

        if startup and profile.startup.name in ANIMATIONS:
            self._renderer.set_base(frame)
            self._renderer.play_one_shot(
                profile.startup.name, _animation_config(profile.startup),
                duration=STARTUP_SECONDS, on_done=lambda: self._defer(start_ambient))
        elif transition in TRANSITIONS:
            # Capture the visible frame before replacing what is underneath.
            self._renderer.start_transition(
                transition, frame, duration=TRANSITION_SECONDS,
                cfg=TransitionConfig(duration=TRANSITION_SECONDS),
                on_complete=lambda: self._defer(start_ambient))
            self._renderer.stop_ambient()
            self._renderer.set_base(frame)
        else:
            self._renderer.set_base(frame)
            same = (previous is not None and ambient is not None
                    and previous.ambient.name == ambient.name
                    and self._renderer.ambient_name() == ambient.name)
            if same:
                self._renderer.update_ambient_config(**asdict(_animation_config(ambient)))
            else:
                self._renderer.stop_ambient()
                start_ambient()

    # ---------- device ----------
    def poll_device(self) -> bool:
        present = device_present()
        if present and not self._kb.is_connected and not self._settling:
            self._settling = True
            GLib.timeout_add_seconds(SETTLE_SECONDS, self._connect_after_settling)
        elif not present and self._kb.is_connected:
            logger.info("keyboard disconnected")
            self.disconnect()
        if self._kb.is_connected and self._needs_key_reader() and not (
                self._reader and self._reader.is_alive()):
            self._start_reader()
        return True

    def _connect_after_settling(self) -> bool:
        self._settling = False
        self.connect()
        return False

    def connect(self) -> bool:
        denied = self.status.access_denied
        try:
            self._kb.connect()
        except KeyboardNotFoundError as e:
            logger.debug("not connected: %s", e)
            return False
        except OSError as e:
            self.status.access_denied = isinstance(e, PermissionError)
            if not denied:
                logger.warning("cannot open the keyboard: %s", e)
            self.emit_status()
            return False
        self.status.connected, self.status.access_denied = True, False
        logger.info("keyboard connected")
        self._renderer.start()
        self.poll_battery()
        target = (self.find_profile(self._chosen or "") or self._current
                  or self.find_profile(get_last_profile() or ""))
        if target is None:
            if not self._profiles:
                profile = create_default_profile()
                profile.save()
                self._profiles = [profile]
            target = self._profiles[0]
        self._current = target
        self.set_profile(target.name, reason="reconnect")
        self._apply_rules()
        return True

    def disconnect(self) -> None:
        self._stop_reader()
        self._renderer.stop_ambient()
        self._renderer.stop()
        self._kb.disconnect()
        self.status.connected = False
        self.status.battery_percent = -1
        self.status.battery_charging = False
        self.emit_status()

    def poll_battery(self) -> bool:
        if self._kb.is_connected:
            try:
                result = self._kb.get_battery()
            except OSError as e:
                logger.debug("battery query failed: %s", e)
                result = None
            if result is not None:
                before = (self.status.battery_percent, self.status.battery_charging)
                self.status.battery_percent, self.status.battery_charging = result
                if before != result:
                    self.emit_status()
        return True

    # ---------- final pass over every frame (renderer thread) ----------
    def _post_process(self, frame: dict) -> dict:
        if self._locked and self.options["off_when_locked"]:
            return BLACK_FRAME
        low = 0 <= self.status.battery_percent <= LOW_BATTERY
        if self.options["battery_gkeys"] and low and not self.status.battery_charging:
            frame = {**frame, **dict.fromkeys(GKEYS, (255, 0, 0))}
        if self._idle:
            frame = {a: tuple(int(v * IDLE_BRIGHTNESS) for v in c) for a, c in frame.items()}
        return frame

    def set_locked(self, locked: bool) -> None:
        self._locked = bool(locked)
        if not locked:
            self._renderer.invalidate()

    def resumed(self) -> None:
        self._renderer.invalidate()

    # ---------- options ----------
    def set_option(self, name: str, value) -> bool:
        if not set_option(name, value):
            return False
        self.options = get_options()
        if name == "idle_minutes":
            self.start_idle_watch()
        return True

    def start_idle_watch(self) -> None:
        if self._idle_watch is not None:
            watcher, source = self._idle_watch
            self._idle_watch = None
            GLib.source_remove(source)
            watcher.close()
        self._idle = False
        minutes = self.options["idle_minutes"]
        if minutes <= 0:
            return
        try:
            watcher = IdleWatcher(minutes * 60, self._set_idle)
        except OSError as e:
            logger.info("idle dimming unavailable: %s", e)
            self._idle_unavailable()
            return

        def ready(_fd, condition) -> bool:
            if condition & (GLib.IO_HUP | GLib.IO_ERR) or not watcher.dispatch():
                watcher.close()
                self._idle_watch = None
                self._idle = False
                self._idle_unavailable()
                return False
            return True

        source = GLib.io_add_watch(watcher.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, ready)
        self._idle_watch = (watcher, source)
        self.status.idle_available = True

    def _idle_unavailable(self) -> None:
        self.status.idle_available = False
        self.emit_status()

    def _set_idle(self, idle: bool) -> None:
        self._idle = idle

    def _needs_key_reader(self) -> bool:
        profile = self._shown
        if profile is None:
            return False

        reactive_enabled = bool(profile.reactive.effect)
        gkey_actions_enabled = bool(self._gkey_actions)

        return reactive_enabled or gkey_actions_enabled

    # ---------- typing effects ----------
    def _configure_reactive(self) -> None:
        cfg = self._shown.reactive if self._shown else None

        if cfg is None or not cfg.effect:
            self._reactive = None
            self._renderer.set_reactive_source(None)
        else:
            if self._reactive is None:
                self._reactive = ReactiveOverlay(
                    cfg.effect, cfg.color, cfg.intensity
                )
                self._renderer.set_reactive_source(self._reactive)
            else:
                self._reactive.effect = cfg.effect
                self._reactive.color = cfg.color
                self._reactive.intensity = cfg.intensity

        if self._needs_key_reader() and self._kb.is_connected:
            if not (self._reader and self._reader.is_alive()):
                self._start_reader()
        else:
            self._stop_reader()

    def _start_reader(self) -> None:
        self._stop_reader()
        ok = False
        if HAVE_EVDEV:
            reader = KeyEventReader(self._key_pressed)
            ok = reader.start(find_keyboard_event_devices())
            if ok:
                self._reader = reader
            else:
                reader.stop()
        if ok != self.status.typing_available:
            self.status.typing_available = ok
            self.emit_status()

    def _stop_reader(self) -> None:
        if self._reader is not None:
            self._reader.stop()
            self._reader = None

    def _key_pressed(self, address: int) -> None:
        overlay = self._reactive
        if overlay is not None:
            overlay.trigger(address)

        self._defer(self._handle_key_pressed, address)

    def _handle_key_pressed(self, address: int) -> None:
        if self._previewing:
            return

        target = get_profile_switch_target(self._gkey_actions, address)
        if target is not None:
            self.set_profile(target, reason="gkey")

    # ---------- application rules ----------
    def reload_rules(self) -> None:
        self.rules = AutoSwitchRules.load()
        self._last_window = ("", "")
        if self._window_source is not None:
            self._window_source.stop()
            self._window_source = None
        if self.rules.enabled and detect_compositor() == "kwin":
            script = find_kwin_script()
            if script is not None:
                source = KWinSource(script)
                if source.start(self.window_changed):
                    self._window_source = source
        self.status.auto_switch = self._window_source is not None
        self.emit_status()

    def window_changed(self, win_class: str, title: str) -> None:
        if win_class == APP_ID:
            # The editor and its dialogs: keep showing the profile being edited.
            return
        if (win_class, title) == self._last_window:
            return
        self._last_window = (win_class, title)
        self._apply_rules()

    def _apply_rules(self) -> None:
        """Show the profile for the active window, or the chosen one when no rule matches."""
        win_class, title = self._last_window
        if not self.rules.enabled or self._previewing or not (win_class or title):
            return
        rule = self.rules.match(win_class, title)
        if rule is not None:
            target, transition = rule.profile, rule.transition or self.rules.transition
        elif self.rules.fallback and self.find_profile(self.rules.fallback):
            target, transition = self.rules.fallback, self.rules.transition
        elif self._chosen is not None:
            target, transition = self._chosen, self.rules.transition
        else:
            return
        if self._current is None or self._current.name != target:
            self.set_profile(target, transition, reason=f"window:{win_class}")

    # ---------- lifecycle ----------
    def emit_status(self) -> None:
        self.on_status(asdict(self.status))

    def boot(self) -> None:
        self.reload_profiles()
        self.start_idle_watch()
        self.reload_rules()
        self.poll_device()

    def shutdown(self) -> None:
        if self._window_source is not None:
            self._window_source.stop()
        self.disconnect()


class Service(dbus.service.Object):
    """The D-Bus face of :class:`Controller`."""

    def __init__(self, bus, name, controller: Controller, quit_loop) -> None:
        super().__init__(name, OBJECT_PATH)
        self._bus = bus
        self._c = controller
        self._quit = quit_loop
        self._preview_watch = None
        controller.on_status = lambda s: self.StatusChanged(json.dumps(s))
        controller.on_switched = self.ProfileSwitched

    @dbus.service.method(BUS_NAME, in_signature="ss", out_signature="b")
    def SetProfile(self, name, transition):
        return self._c.set_profile(str(name), str(transition))

    @dbus.service.method(BUS_NAME, in_signature="s", out_signature="b", sender_keyword="sender")
    def PreviewProfile(self, payload, sender=None):
        if sender and self._preview_watch is None:
            # Drop the preview if the editor goes away, even by crashing.
            self._preview_watch = self._bus.watch_name_owner(sender, self._preview_owner)
        return self._c.preview(str(payload))

    def _preview_owner(self, owner) -> None:
        if not owner:
            if self._preview_watch is not None:
                self._preview_watch.cancel()
                self._preview_watch = None
            self._c.stop_preview()

    @dbus.service.method(BUS_NAME, in_signature="", out_signature="")
    def StopPreview(self):
        self._c.stop_preview()

    @dbus.service.method(BUS_NAME, in_signature="", out_signature="s")
    def ReloadProfiles(self):
        return json.dumps(self._c.reload_profiles())

    @dbus.service.method(BUS_NAME, in_signature="", out_signature="")
    def ReloadGKeyActions(self):
        self._c.reload_gkey_actions()

    @dbus.service.method(BUS_NAME, in_signature="", out_signature="")
    def ReloadRules(self):
        self._c.reload_rules()

    @dbus.service.method(BUS_NAME, in_signature="", out_signature="s")
    def GetStatus(self):
        return json.dumps(asdict(self._c.status))

    @dbus.service.method(BUS_NAME, in_signature="ss", out_signature="b")
    def SetOption(self, name, value_json):
        try:
            return self._c.set_option(str(name), json.loads(str(value_json)))
        except ValueError:
            return False

    @dbus.service.method(BUS_NAME, in_signature="ss", out_signature="")
    def OnActiveWindowChanged(self, win_class, title):
        self._c.window_changed(str(win_class), str(title))

    @dbus.service.method(BUS_NAME, in_signature="", out_signature="s",
                         async_callbacks=("reply", "error"))
    def PickWindow(self, reply, error):
        """Let the person click a window and return its application class."""
        try:
            kwin = self._bus.get_object("org.kde.KWin", "/KWin")
        except dbus.DBusException as e:
            error(e)
            return
        kwin.queryWindowInfo(
            dbus_interface="org.kde.KWin", timeout=120,
            reply_handler=lambda info: reply(str(info.get("resourceClass", ""))),
            error_handler=error)

    @dbus.service.method(BUS_NAME, in_signature="", out_signature="")
    def Quit(self):
        GLib.idle_add(self._quit)

    @dbus.service.signal(BUS_NAME, signature="s")
    def StatusChanged(self, status):
        pass

    @dbus.service.signal(BUS_NAME, signature="ss")
    def ProfileSwitched(self, name, reason):
        pass


def _watch_session(bus, controller: Controller) -> None:
    bus.add_signal_receiver(controller.set_locked, "ActiveChanged",
                            "org.freedesktop.ScreenSaver", path="/ScreenSaver")

    def sleeping(starting) -> None:
        if not starting:
            controller.resumed()

    try:
        dbus.SystemBus().add_signal_receiver(
            sleeping, "PrepareForSleep", "org.freedesktop.login1.Manager",
            "org.freedesktop.login1")
    except dbus.DBusException as e:
        logger.info("cannot watch for suspend: %s", e)


def run(controller: Controller | None = None) -> int:
    configure_logging("daemon")
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    try:
        name = dbus.service.BusName(BUS_NAME, bus, do_not_queue=True)
    except dbus.exceptions.NameExistsException:
        logger.error("already running")
        return 1
    logger.info("starting (pid %d)", os.getpid())
    loop = GLib.MainLoop()
    controller = controller or Controller()
    service = Service(bus, name, controller, loop.quit)  # noqa: F841 (kept alive)
    _watch_session(bus, controller)
    for sig in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, loop.quit)
    controller.boot()
    GLib.timeout_add_seconds(POLL_SECONDS, controller.poll_device)
    GLib.timeout_add_seconds(BATTERY_SECONDS, controller.poll_battery)
    try:
        loop.run()
    finally:
        controller.shutdown()
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
