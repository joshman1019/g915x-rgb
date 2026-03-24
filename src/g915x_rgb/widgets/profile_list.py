"""Profile list sidebar widget."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from ..profile import Profile


class ProfileList(Gtk.Box):
    """Sidebar list of profiles with add/delete controls."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._profiles: list[Profile] = []
        self._on_profile_selected = None
        self._selected_index = -1

        self.set_size_request(180, -1)
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        self.set_margin_start(4)
        self.set_margin_end(4)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        label = Gtk.Label(label="Profiles", xalign=0)
        label.add_css_class("heading")
        label.set_hexpand(True)
        header.append(label)

        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.add_css_class("flat")
        add_btn.connect("clicked", self._on_add)
        header.append(add_btn)

        del_btn = Gtk.Button(icon_name="list-remove-symbolic")
        del_btn.add_css_class("flat")
        del_btn.connect("clicked", self._on_delete)
        header.append(del_btn)

        self.append(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scrolled)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.add_css_class("navigation-sidebar")
        self._listbox.connect("row-selected", self._on_row_selected)
        scrolled.set_child(self._listbox)

    def set_profiles(self, profiles: list[Profile]) -> None:
        self._profiles = profiles
        self._rebuild_list()
        if profiles:
            self._listbox.select_row(self._listbox.get_row_at_index(0))

    def get_selected_profile(self) -> Profile | None:
        if 0 <= self._selected_index < len(self._profiles):
            return self._profiles[self._selected_index]
        return None

    def update_selected_profile(self, profile: Profile) -> None:
        if 0 <= self._selected_index < len(self._profiles):
            self._profiles[self._selected_index] = profile

    def refresh_selected_label(self) -> None:
        """Update the displayed name of the selected profile row."""
        if 0 <= self._selected_index < len(self._profiles):
            row = self._listbox.get_row_at_index(self._selected_index)
            if row:
                label = row.get_child()
                label.set_text(self._profiles[self._selected_index].name)

    def connect_profile_selected(self, callback) -> None:
        self._on_profile_selected = callback

    def _rebuild_list(self) -> None:
        while True:
            row = self._listbox.get_row_at_index(0)
            if row is None:
                break
            self._listbox.remove(row)

        for profile in self._profiles:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=profile.name, xalign=0)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            label.set_margin_start(8)
            label.set_margin_end(8)
            row.set_child(label)
            self._listbox.append(row)

    def _on_row_selected(self, listbox, row) -> None:
        if row is None:
            self._selected_index = -1
            return
        self._selected_index = row.get_index()
        if self._on_profile_selected and 0 <= self._selected_index < len(self._profiles):
            self._on_profile_selected(self._profiles[self._selected_index])

    def _on_add(self, btn) -> None:
        name = f"Profile {len(self._profiles) + 1}"
        new_profile = Profile(name=name)
        new_profile.group_colors["keys"] = (255, 255, 255)
        self._profiles.append(new_profile)
        self._rebuild_list()
        last = self._listbox.get_row_at_index(len(self._profiles) - 1)
        self._listbox.select_row(last)

    def _on_delete(self, btn) -> None:
        if self._selected_index < 0 or len(self._profiles) <= 1:
            return
        self._profiles.pop(self._selected_index)
        self._rebuild_list()
        idx = min(self._selected_index, len(self._profiles) - 1)
        self._listbox.select_row(self._listbox.get_row_at_index(idx))
