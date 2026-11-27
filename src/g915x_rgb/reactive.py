"""Reactive typing overlay: keypress -> visual effect on the keyboard.

The ``KeyEventReader`` thread reads from a Linux evdev device (the
keyboard's ``-event-kbd`` node under ``/dev/input/by-id``) and posts
each keypress to the configured :class:`ReactiveOverlay`. The overlay
exposes itself as a :data:`ReactiveSource` callable that the renderer
samples once per tick.

Design choice — reactive returns ``(color, alpha)`` per key rather than
absolute colors so it composes correctly over an ambient animation: a
fading glow blends with whatever ambient is producing underneath it,
instead of cutting through to the static base.

If python-evdev isn't installed, the module imports cleanly but
``KeyEventReader`` will raise on construction. The daemon detects this
and disables reactive features for the session.
"""

from __future__ import annotations

import glob
import logging
import math
import os
import select
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from .animation import RGB
from .keyboard_layout import G915X_KEYS, KEY_BY_NAME

logger = logging.getLogger("g915x.reactive")

try:
    import evdev
    from evdev import ecodes  # noqa: F401
    HAVE_EVDEV = True
except ImportError:
    evdev = None  # type: ignore[assignment]
    HAVE_EVDEV = False


# =====================================================================
# Linux evdev keycode → Logitech address
# =====================================================================

# Hand-mapped from <linux/input-event-codes.h>. Only the keys present on
# the G915 X layout are listed; anything else falls through to None.
_EVDEV_TO_NAME: dict[int, str] = {
    1: "Esc",
    2: "1", 3: "2", 4: "3", 5: "4", 6: "5",
    7: "6", 8: "7", 9: "8", 10: "9", 11: "0",
    12: "-", 13: "=", 14: "Bksp", 15: "Tab",
    16: "Q", 17: "W", 18: "E", 19: "R", 20: "T",
    21: "Y", 22: "U", 23: "I", 24: "O", 25: "P",
    26: "[", 27: "]", 28: "Enter", 29: "LCtrl",
    30: "A", 31: "S", 32: "D", 33: "F", 34: "G",
    35: "H", 36: "J", 37: "K", 38: "L", 39: ";",
    40: "'", 41: "`", 42: "LShift", 43: "\\",
    44: "Z", 45: "X", 46: "C", 47: "V", 48: "B",
    49: "N", 50: "M", 51: ",", 52: ".", 53: "/",
    54: "RShift", 55: "Num*", 56: "LAlt", 57: "Space",
    58: "Caps",
    59: "F1", 60: "F2", 61: "F3", 62: "F4", 63: "F5",
    64: "F6", 65: "F7", 66: "F8", 67: "F9", 68: "F10",
    69: "NmLk", 70: "ScrLk",
    71: "Num7", 72: "Num8", 73: "Num9", 74: "Num-",
    75: "Num4", 76: "Num5", 77: "Num6", 78: "Num+",
    79: "Num1", 80: "Num2", 81: "Num3",
    82: "Num0", 83: "Num.",
    87: "F11", 88: "F12",
    # Confirmed G1-G9 mapping to Linux F13-F21 evdev codes.
    183: "G1", 184: "G2", 185: "G3",
    186: "G4", 187: "G5", 188: "G6",
    189: "G7", 190: "G8", 191: "G9",
    96: "NumEnt", 97: "RCtrl", 98: "Num/", 99: "PrtSc",
    100: "RAlt",
    102: "Home", 103: "Up", 104: "PgUp",
    105: "Left", 106: "Right",
    107: "End", 108: "Down", 109: "PgDn",
    110: "Ins", 111: "Del",
    113: "Mute",
    119: "Pause",
    125: "LGui", 127: "Menu",
    163: "Next", 164: "Play", 165: "Prev",
}

EVDEV_TO_ADDR: dict[int, int] = {
    code: KEY_BY_NAME[name].address
    for code, name in _EVDEV_TO_NAME.items()
    if name in KEY_BY_NAME
}

# Spatial info for radial / axial effects
_KEY_X: dict[int, float] = {k.address: k.x + k.w / 2 for k in G915X_KEYS}
_KEY_Y: dict[int, float] = {k.address: k.y + k.h / 2 for k in G915X_KEYS}


# =====================================================================
# evdev device discovery & reader
# =====================================================================

def find_keyboard_event_devices() -> list[str]:
    """The G915 X's own key event device; other keyboards are never read."""
    devices = sorted(glob.glob("/dev/input/by-id/usb-Logitech_G915_X_*-event-kbd"))
    return devices


class KeyEventReader:
    """Reads key presses on a background thread until stopped."""

    def __init__(self, on_press: Callable[[int], None]) -> None:
        if not HAVE_EVDEV:
            raise RuntimeError("python-evdev is not installed")
        self._on_press = on_press
        self._thread: threading.Thread | None = None
        self._wake_r, self._wake_w = os.pipe()

    def start(self, paths: list[str]) -> bool:
        devices = []
        for path in paths:
            try:
                devices.append(evdev.InputDevice(path))
            except OSError as e:
                logger.warning("cannot open %s: %s", path, e)
        if devices:
            self._thread = threading.Thread(target=self._run, args=(devices,),
                                            daemon=True, name="key-reader")
            self._thread.start()
        return bool(devices)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        if self._wake_w < 0:
            return
        os.write(self._wake_w, b"x")
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        os.close(self._wake_w)
        os.close(self._wake_r)
        self._wake_w = self._wake_r = -1

    def _run(self, devices: list) -> None:
        by_fd = {d.fd: d for d in devices}
        try:
            while by_fd:
                ready, _, _ = select.select([*by_fd, self._wake_r], [], [])
                if self._wake_r in ready:
                    return
                for fd in ready:
                    try:
                        self._handle(by_fd[fd].read())
                    except BlockingIOError:
                        continue
                    except OSError:      # unplugged
                        by_fd.pop(fd).close()
        finally:
            for dev in by_fd.values():
                dev.close()

    def _handle(self, events) -> None:
        for event in events:
            # value 1 is a press; releases and autorepeat are ignored.
            if event.type == ecodes.EV_KEY and event.value == 1:
                addr = EVDEV_TO_ADDR.get(event.code)
                if addr is not None:
                    self._on_press(addr)


# =====================================================================
# Reactive overlay sources
# =====================================================================

# Effect lifetimes (seconds)
_LIFE_GLOW = 0.6
_LIFE_RIPPLE = 0.8
_LIFE_STARBURST = 0.5
_LIFE_HEAT = 2.5
MAX_HITS = 64


@dataclass
class _Hit:
    address: int
    started_at: float


class ReactiveOverlay:
    """Aggregates active key effects and renders them as an overlay frame.

    Instances are :data:`~g915x_rgb.renderer.ReactiveSource`-callable —
    the renderer can pass an instance straight to ``set_reactive_source``.
    """

    def __init__(self, effect: str, color: RGB, intensity: float = 1.0) -> None:
        self.effect = effect
        self.color = color
        self.intensity = max(0.0, min(2.0, intensity))
        self._hits: list[_Hit] = []
        self._lock = threading.Lock()

    def trigger(self, address: int) -> None:
        if not self.effect:
            return
        with self._lock:
            self._hits.append(_Hit(address, time.monotonic()))
            del self._hits[:-MAX_HITS]

    def _lifetime(self) -> float:
        return {
            "glow": _LIFE_GLOW,
            "ripple": _LIFE_RIPPLE,
            "starburst": _LIFE_STARBURST,
            "heat": _LIFE_HEAT,
        }.get(self.effect, 0.0)

    def __call__(self, now: float) -> dict[int, tuple[RGB, float]]:
        if not self.effect:
            return {}
        lifetime = self._lifetime()
        if lifetime <= 0:
            return {}

        with self._lock:
            self._hits = [h for h in self._hits if now - h.started_at < lifetime]
            hits = list(self._hits)
        if not hits:
            return {}

        out: dict[int, tuple[RGB, float]] = {}
        for hit in hits:
            age = now - hit.started_at
            t = age / lifetime           # 0..1
            if self.effect == "glow":
                self._compose_glow(hit, t, out)
            elif self.effect == "ripple":
                self._compose_ripple(hit, t, out)
            elif self.effect == "starburst":
                self._compose_starburst(hit, t, out)
            elif self.effect == "heat":
                self._compose_heat(hit, t, out)
        return out

    # --- effect implementations ---

    def _put(self, out: dict[int, tuple[RGB, float]],
             addr: int, alpha: float) -> None:
        """Combine new alpha at ``addr`` with whatever's already there."""
        alpha *= self.intensity
        if alpha <= 0:
            return
        prev = out.get(addr)
        # Combine via take-max so two simultaneous hits don't fade each other.
        if prev is None or alpha > prev[1]:
            out[addr] = (self.color, min(1.0, alpha))

    def _compose_glow(self, hit: _Hit, t: float,
                      out: dict[int, tuple[RGB, float]]) -> None:
        # 1.0 at t=0, eased down to 0 at t=1
        alpha = (1.0 - t) ** 1.4
        self._put(out, hit.address, alpha)

    def _compose_ripple(self, hit: _Hit, t: float,
                        out: dict[int, tuple[RGB, float]]) -> None:
        cx = _KEY_X.get(hit.address)
        cy = _KEY_Y.get(hit.address)
        if cx is None or cy is None:
            return
        front = t * 6.5            # ring expansion radius in key units
        ring_width = 1.2
        global_fade = (1.0 - t) ** 1.2
        for addr, kx in _KEY_X.items():
            ky = _KEY_Y[addr]
            d = math.sqrt((kx - cx) ** 2 + (ky - cy) ** 2)
            ring = abs(d - front)
            if ring < ring_width:
                local = (1.0 - ring / ring_width) ** 2
                self._put(out, addr, local * global_fade)

    def _compose_heat(self, hit: _Hit, t: float,
                      out: dict[int, tuple[RGB, float]]) -> None:
        """Warmth that builds up where you type and slowly cools."""
        cx, cy = _KEY_X.get(hit.address), _KEY_Y.get(hit.address)
        if cx is None or cy is None:
            return
        for addr, kx in _KEY_X.items():
            d = math.hypot(kx - cx, _KEY_Y[addr] - cy)
            if d < 2.2:
                add = (1 - d / 2.2) * (1 - t) * 0.5 * self.intensity
                prev = out.get(addr, (self.color, 0.0))[1]
                out[addr] = (self.color, min(1.0, prev + add))

    def _compose_starburst(self, hit: _Hit, t: float,
                           out: dict[int, tuple[RGB, float]]) -> None:
        cx = _KEY_X.get(hit.address)
        cy = _KEY_Y.get(hit.address)
        if cx is None or cy is None:
            return
        reach = t * 5.0
        global_fade = (1.0 - t) ** 1.5
        for addr, kx in _KEY_X.items():
            ky = _KEY_Y[addr]
            dx = kx - cx
            dy = ky - cy
            ax = abs(dx)
            ay = abs(dy)
            on_axis = (ay < 0.4 and ax > 0) or (ax < 0.4 and ay > 0)
            if not on_axis:
                continue
            d = max(ax, ay)
            edge = abs(d - reach)
            if edge < 0.7:
                local = (1.0 - edge / 0.7) ** 2
                self._put(out, addr, local * global_fade)
