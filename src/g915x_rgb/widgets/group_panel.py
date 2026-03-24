"""Panel for editing group colors."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from ..keyboard_layout import GROUPS, KEY_GROUPS


class GroupPanel(Gtk.Box):
    """Grid of group color buttons."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._color_buttons: dict[str, Gtk.ColorDialogButton] = {}
        self._on_group_changed = None

        self.set_margin_top(8)
        self.set_margin_bottom(8)
        self.set_margin_start(8)
        self.set_margin_end(8)

        label = Gtk.Label(label="Group Colors", xalign=0)
        label.add_css_class("heading")
        self.append(label)

        grid = Gtk.Grid(row_spacing=6, column_spacing=12)
        grid.set_margin_top(8)
        self.append(grid)

        for i, group in enumerate(GROUPS):
            name_label = Gtk.Label(label=group.capitalize(), xalign=0)
            name_label.set_hexpand(True)
            grid.attach(name_label, 0, i, 1, 1)

            count = len(KEY_GROUPS.get(group, []))
            count_label = Gtk.Label(label=f"({count} keys)", xalign=0)
            count_label.add_css_class("dim-label")
            grid.attach(count_label, 1, i, 1, 1)

            btn = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog())
            btn.set_rgba(_rgb_to_rgba(0, 0, 0))
            btn.connect("notify::rgba", self._on_color_changed, group)
            grid.attach(btn, 2, i, 1, 1)
            self._color_buttons[group] = btn

    def set_group_colors(self, colors: dict[str, tuple[int, int, int]]) -> None:
        for group, btn in self._color_buttons.items():
            if group in colors:
                r, g, b = colors[group]
                btn.set_rgba(_rgb_to_rgba(r, g, b))

    def get_group_colors(self) -> dict[str, tuple[int, int, int]]:
        result = {}
        for group, btn in self._color_buttons.items():
            rgba = btn.get_rgba()
            result[group] = (
                int(rgba.red * 255),
                int(rgba.green * 255),
                int(rgba.blue * 255),
            )
        return result

    def connect_group_changed(self, callback) -> None:
        self._on_group_changed = callback

    def _on_color_changed(self, btn, pspec, group: str) -> None:
        if self._on_group_changed:
            rgba = btn.get_rgba()
            color = (int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
            self._on_group_changed(group, color)


class KeyPanel(Gtk.Box):
    """Panel for editing individual key colors."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._on_key_color_changed = None

        self.set_margin_top(8)
        self.set_margin_bottom(8)
        self.set_margin_start(8)
        self.set_margin_end(8)

        self._title = Gtk.Label(label="Per-Key Colors", xalign=0)
        self._title.add_css_class("heading")
        self.append(self._title)

        self._info = Gtk.Label(label="Click a key on the keyboard to select it", xalign=0)
        self._info.add_css_class("dim-label")
        self._info.set_wrap(True)
        self.append(self._info)

        # Color picker for selected key(s)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        self.append(box)

        self._key_name_label = Gtk.Label(label="No key selected", xalign=0)
        self._key_name_label.set_hexpand(True)
        self._key_name_label.set_ellipsize(3)  # Pango.EllipsizeMode.END
        self._key_name_label.set_max_width_chars(40)
        box.append(self._key_name_label)

        dialog = Gtk.ColorDialog()
        self._color_btn = Gtk.ColorDialogButton(dialog=dialog)
        self._color_btn.set_rgba(_rgb_to_rgba(255, 255, 255))
        self._color_btn.connect("notify::rgba", self._on_color_picked)
        self._color_btn.set_sensitive(False)
        box.append(self._color_btn)

        # Clear individual color button
        self._clear_btn = Gtk.Button(label="Reset to Group")
        self._clear_btn.connect("clicked", self._on_clear)
        self._clear_btn.set_sensitive(False)
        self.append(self._clear_btn)

        self._selected_addresses: set[int] = set()
        self._on_clear_callback = None

    def set_selected_keys(self, addresses: set[int], names: list[str],
                          color: tuple[int, int, int] | None) -> None:
        self._selected_addresses = addresses
        if not addresses:
            self._key_name_label.set_text("No key selected")
            self._color_btn.set_sensitive(False)
            self._clear_btn.set_sensitive(False)
        else:
            # Truncate long lists to prevent window growth
            if len(names) > 5:
                display = ", ".join(names[:5]) + f" +{len(names)-5} more"
            else:
                display = ", ".join(names)
            self._key_name_label.set_text(display)
            self._color_btn.set_sensitive(True)
            self._clear_btn.set_sensitive(True)
            if color:
                self._color_btn.set_rgba(_rgb_to_rgba(*color))

    def connect_key_color_changed(self, callback) -> None:
        self._on_key_color_changed = callback

    def connect_clear_key(self, callback) -> None:
        self._on_clear_callback = callback

    def _on_color_picked(self, btn, pspec) -> None:
        if not self._selected_addresses or not self._on_key_color_changed:
            return
        rgba = btn.get_rgba()
        color = (int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
        self._on_key_color_changed(self._selected_addresses, color)

    def _on_clear(self, btn) -> None:
        if self._on_clear_callback and self._selected_addresses:
            self._on_clear_callback(self._selected_addresses)


def _rgb_to_rgba(r: int, g: int, b: int) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.red = r / 255
    rgba.green = g / 255
    rgba.blue = b / 255
    rgba.alpha = 1.0
    return rgba
