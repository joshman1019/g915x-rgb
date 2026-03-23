"""GTK4 DrawingArea widget that renders the G915 X keyboard layout.

Keys are drawn as rounded rectangles, colored according to the current profile.
Supports click-to-select for per-key color editing.
"""

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk, Graphene

from .keyboard_layout import (
    G915X_KEYS,
    KEY_BY_ADDRESS,
    KEY_GROUPS,
    LAYOUT_HEIGHT,
    LAYOUT_WIDTH,
    KeyDef,
)

KEY_PADDING = 0.06  # Gap between keys (key units)
KEY_RADIUS = 0.12   # Corner radius (key units)
LABEL_SIZE = 0.35   # Font size (key units)
MIN_WIDGET_WIDTH = 1050
MIN_WIDGET_HEIGHT = 300


class KeyboardWidget(Gtk.DrawingArea):
    """Interactive keyboard visualization widget."""

    def __init__(self):
        super().__init__()
        self._key_colors: dict[int, tuple[int, int, int]] = {}
        self._selected_keys: set[int] = set()
        self._hovered_key: int | None = None
        self._scale = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._on_key_selected = None  # callback(address)

        self.set_content_width(MIN_WIDGET_WIDTH)
        self.set_content_height(MIN_WIDGET_HEIGHT)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.set_draw_func(self._draw)

        # Click handler
        click = Gtk.GestureClick.new()
        click.connect("pressed", self._on_click)
        self.add_controller(click)

        # Hover handler
        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

    def set_key_colors(self, colors: dict[int, tuple[int, int, int]]) -> None:
        self._key_colors = colors
        self.queue_draw()

    def set_selected_keys(self, addresses: set[int]) -> None:
        self._selected_keys = addresses
        self.queue_draw()

    def connect_key_selected(self, callback) -> None:
        self._on_key_selected = callback

    def _compute_transform(self, width: float, height: float) -> None:
        margin = 10
        usable_w = width - 2 * margin
        usable_h = height - 2 * margin

        scale_x = usable_w / LAYOUT_WIDTH
        scale_y = usable_h / LAYOUT_HEIGHT
        self._scale = min(scale_x, scale_y)

        total_w = LAYOUT_WIDTH * self._scale
        total_h = LAYOUT_HEIGHT * self._scale
        self._offset_x = margin + (usable_w - total_w) / 2
        self._offset_y = margin + (usable_h - total_h) / 2

    def _key_rect(self, key: KeyDef) -> tuple[float, float, float, float]:
        x = self._offset_x + key.x * self._scale
        y = self._offset_y + (key.y + 0.5) * self._scale  # +0.5 for logo row offset
        w = key.w * self._scale
        h = key.h * self._scale
        pad = KEY_PADDING * self._scale
        return (x + pad, y + pad, w - 2 * pad, h - 2 * pad)

    def _key_at_point(self, px: float, py: float) -> KeyDef | None:
        for key in G915X_KEYS:
            x, y, w, h = self._key_rect(key)
            if x <= px <= x + w and y <= py <= y + h:
                return key
        return None

    def _draw(self, area: Gtk.DrawingArea, cr: cairo.Context,
              width: int, height: int) -> None:
        self._compute_transform(width, height)

        # Background
        cr.set_source_rgb(0.12, 0.12, 0.14)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # Draw keyboard plate
        plate_x = self._offset_x - 5
        plate_y = self._offset_y - 5
        plate_w = LAYOUT_WIDTH * self._scale + 10
        plate_h = LAYOUT_HEIGHT * self._scale + 10
        _rounded_rect(cr, plate_x, plate_y, plate_w, plate_h, 8)
        cr.set_source_rgb(0.18, 0.18, 0.20)
        cr.fill()

        # Draw keys
        for key in G915X_KEYS:
            self._draw_key(cr, key)

    def _draw_key(self, cr: cairo.Context, key: KeyDef) -> None:
        x, y, w, h = self._key_rect(key)
        radius = KEY_RADIUS * self._scale
        is_selected = key.address in self._selected_keys
        is_hovered = key.address == self._hovered_key

        r, g, b = self._key_colors.get(key.address, (40, 40, 45))
        fr, fg, fb = r / 255, g / 255, b / 255
        brightness = max(fr, fg, fb)

        # Key body — dark base with colored fill
        _rounded_rect(cr, x, y, w, h, radius)
        cr.set_source_rgb(0.06, 0.06, 0.08)
        cr.fill()

        # Colored surface (slightly inset for 3D effect)
        inset = 1.0
        _rounded_rect(cr, x + inset, y + inset, w - 2 * inset, h - 2 * inset, max(radius - 1, 1))
        if brightness > 0.05:
            cr.set_source_rgb(fr * 0.35, fg * 0.35, fb * 0.35)
        else:
            cr.set_source_rgb(0.12, 0.12, 0.14)
        cr.fill()

        # LED color dot/stripe at top of key
        if brightness > 0.05:
            led_h = max(h * 0.18, 2)
            _rounded_rect(cr, x + inset + 2, y + inset + 1, w - 2 * inset - 4, led_h, 2)
            cr.set_source_rgb(fr, fg, fb)
            cr.fill()

        # Selection highlight
        if is_selected:
            _rounded_rect(cr, x - 1, y - 1, w + 2, h + 2, radius + 1)
            cr.set_source_rgba(1.0, 1.0, 0.3, 0.9)
            cr.set_line_width(2.0)
            cr.stroke()
        elif is_hovered:
            _rounded_rect(cr, x, y, w, h, radius)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.25)
            cr.set_line_width(1.0)
            cr.stroke()

        # Key label
        label = key.label if key.label else key.name
        font_size = LABEL_SIZE * self._scale
        if len(label) > 3:
            font_size *= 0.75
        if key.w < 0.6 or key.h < 0.6:
            font_size *= 0.6
        cr.set_font_size(font_size)
        cr.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)

        extents = cr.text_extents(label)
        tx = x + (w - extents.width) / 2 - extents.x_bearing
        ty = y + (h - extents.height) / 2 - extents.y_bearing + h * 0.08

        cr.set_source_rgba(0.85, 0.85, 0.88, 0.9)
        cr.move_to(tx, ty)
        cr.show_text(label)

    def _on_click(self, gesture: Gtk.GestureClick, n_press: int,
                  x: float, y: float) -> None:
        key = self._key_at_point(x, y)
        if key is None:
            self._selected_keys.clear()
            self.queue_draw()
            if self._on_key_selected:
                self._on_key_selected(None)
            return

        state = gesture.get_current_event_state()
        shift_held = bool(state & Gdk.ModifierType.SHIFT_MASK)

        if shift_held:
            if key.address in self._selected_keys:
                self._selected_keys.discard(key.address)
            else:
                self._selected_keys.add(key.address)
        else:
            self._selected_keys = {key.address}

        self.queue_draw()
        if self._on_key_selected:
            self._on_key_selected(key.address)

    def _on_motion(self, controller: Gtk.EventControllerMotion,
                   x: float, y: float) -> None:
        key = self._key_at_point(x, y)
        new_hovered = key.address if key else None
        if new_hovered != self._hovered_key:
            self._hovered_key = new_hovered
            self.queue_draw()

    def _on_leave(self, controller: Gtk.EventControllerMotion) -> None:
        if self._hovered_key is not None:
            self._hovered_key = None
            self.queue_draw()


def _rounded_rect(cr: cairo.Context, x: float, y: float,
                  w: float, h: float, r: float) -> None:
    """Draw a rounded rectangle path."""
    import math
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()
