"""Main application window."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

import threading
import time

from .animation import play_arch_animation
from .backend import G915XBackend, KeyboardNotFoundError
from .config import set_last_profile
from .keyboard_layout import KEY_BY_ADDRESS, KEY_GROUPS, G915X_KEYS
from .keyboard_widget import KeyboardWidget
from .profile import Profile, create_default_profile, load_all_profiles
from .widgets.group_panel import GroupPanel, KeyPanel
from .widgets.profile_list import ProfileList


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="G915 X RGB Controller")
        self.set_default_size(1280, 720)

        self._backend = G915XBackend()
        self._current_profile: Profile | None = None

        self._build_ui()
        self._load_profiles()
        self._try_connect()

    def _build_ui(self) -> None:
        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        self._status_label = Gtk.Label(label="Disconnected")
        self._status_label.add_css_class("dim-label")
        header.pack_end(self._status_label)

        apply_btn = Gtk.Button(label="Apply")
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", self._on_apply)
        header.pack_end(apply_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)

        reconnect_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        reconnect_btn.set_tooltip_text("Reconnect keyboard")
        reconnect_btn.connect("clicked", lambda b: self._try_connect())
        header.pack_end(reconnect_btn)

        main_box.append(header)

        # Content: sidebar + main area
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        main_box.append(paned)

        # Sidebar: profile list
        self._profile_list = ProfileList()
        self._profile_list.connect_profile_selected(self._on_profile_selected)
        sidebar_frame = Gtk.Frame()
        sidebar_frame.set_child(self._profile_list)
        paned.set_start_child(sidebar_frame)
        paned.set_shrink_start_child(False)

        # Right side: keyboard + controls
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        paned.set_end_child(right_box)
        paned.set_shrink_end_child(False)

        # Keyboard visualization
        self._keyboard_widget = KeyboardWidget()
        self._keyboard_widget.connect_key_selected(self._on_key_clicked)
        kbd_frame = Gtk.Frame()
        kbd_frame.set_margin_start(8)
        kbd_frame.set_margin_end(8)
        kbd_frame.set_margin_top(8)
        kbd_frame.set_child(self._keyboard_widget)
        right_box.append(kbd_frame)

        # Bottom controls: stack with Group, Per-Key, and Settings tabs
        stack = Gtk.Stack()
        stack.set_margin_start(8)
        stack.set_margin_end(8)
        stack.set_margin_bottom(8)

        self._group_panel = GroupPanel()
        self._group_panel.connect_group_changed(self._on_group_color_changed)
        stack.add_titled(self._group_panel, "groups", "Groups")

        self._key_panel = KeyPanel()
        self._key_panel.connect_key_color_changed(self._on_key_color_changed)
        self._key_panel.connect_clear_key(self._on_clear_key_color)
        stack.add_titled(self._key_panel, "keys", "Per-Key")

        # Settings tab with animation toggle
        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        settings_box.set_margin_top(8)
        settings_box.set_margin_start(8)
        settings_label = Gtk.Label(label="Profile Settings", xalign=0)
        settings_label.add_css_class("heading")
        settings_box.append(settings_label)

        anim_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        anim_row.set_margin_top(8)
        anim_label = Gtk.Label(label="ARCH startup animation", xalign=0)
        anim_label.set_hexpand(True)
        anim_row.append(anim_label)
        anim_desc = Gtk.Label(
            label="Types A-R-C-H in white, flashes blue, then applies profile",
            xalign=0,
        )
        anim_desc.add_css_class("dim-label")

        self._anim_switch = Gtk.Switch()
        self._anim_switch.connect("notify::active", self._on_anim_toggled)
        anim_row.append(self._anim_switch)
        settings_box.append(anim_row)
        settings_box.append(anim_desc)

        stack.add_titled(settings_box, "settings", "Settings")

        switcher = Gtk.StackSwitcher(stack=stack)
        switcher.set_halign(Gtk.Align.CENTER)
        switcher.set_margin_top(8)
        right_box.append(switcher)
        right_box.append(stack)

    def _try_connect(self) -> None:
        try:
            self._backend.connect()
            self._status_label.set_text("Connected")
            self._status_label.remove_css_class("dim-label")
            self._status_label.add_css_class("success")
        except KeyboardNotFoundError as e:
            self._status_label.set_text("Disconnected")
            self._status_label.remove_css_class("success")
            self._status_label.add_css_class("dim-label")

    def _load_profiles(self) -> None:
        profiles = load_all_profiles()
        if not profiles:
            profiles = [create_default_profile()]
            profiles[0].save()
        self._profile_list.set_profiles(profiles)

    def _on_profile_selected(self, profile: Profile) -> None:
        self._current_profile = profile
        self._group_panel.set_group_colors(profile.group_colors)
        self._anim_switch.set_active(profile.startup_animation)
        self._refresh_keyboard_view()

    def _on_group_color_changed(self, group: str, color: tuple[int, int, int]) -> None:
        if not self._current_profile:
            return
        self._current_profile.group_colors[group] = color
        self._refresh_keyboard_view()

    def _on_key_clicked(self, address: int | None) -> None:
        if address is None:
            self._key_panel.set_selected_keys(set(), [], None)
            return

        selected = self._keyboard_widget._selected_keys
        names = []
        for addr in selected:
            if addr in KEY_BY_ADDRESS:
                names.append(KEY_BY_ADDRESS[addr].name)

        color = None
        if self._current_profile and address in self._current_profile.key_colors:
            color = self._current_profile.key_colors[address]
        elif self._current_profile:
            color = self._current_profile.get_effective_color(address)

        self._key_panel.set_selected_keys(selected, names, color)

    def _on_key_color_changed(self, addresses: set[int],
                              color: tuple[int, int, int]) -> None:
        if not self._current_profile:
            return
        for addr in addresses:
            self._current_profile.key_colors[addr] = color
        self._refresh_keyboard_view()

    def _on_clear_key_color(self, addresses: set[int]) -> None:
        if not self._current_profile:
            return
        for addr in addresses:
            self._current_profile.key_colors.pop(addr, None)
        self._refresh_keyboard_view()

    def _on_anim_toggled(self, switch, pspec) -> None:
        if self._current_profile:
            self._current_profile.startup_animation = switch.get_active()

    def _refresh_keyboard_view(self) -> None:
        if not self._current_profile:
            return
        colors = self._current_profile.get_all_key_colors()
        self._keyboard_widget.set_key_colors(colors)

    def _on_apply(self, btn) -> None:
        if not self._current_profile:
            return
        if not self._backend.is_connected:
            self._try_connect()
            if not self._backend.is_connected:
                return

        # Sync group colors from the panel to the profile
        self._current_profile.group_colors = self._group_panel.get_group_colors()
        colors = self._current_profile.get_all_key_colors()

        set_last_profile(self._current_profile.name)

        run_animation = self._current_profile.startup_animation

        def _apply_in_thread():
            if run_animation:
                play_arch_animation(self._backend)
            self._backend.set_all_keys(0, 0, 0)
            time.sleep(0.1)
            self._backend.apply_key_colors(colors)

        threading.Thread(target=_apply_in_thread, daemon=True).start()

    def _on_save(self, btn) -> None:
        if not self._current_profile:
            return
        # Sync group colors from panel
        self._current_profile.group_colors = self._group_panel.get_group_colors()
        path = self._current_profile.save()
        self._profile_list.update_selected_profile(self._current_profile)
