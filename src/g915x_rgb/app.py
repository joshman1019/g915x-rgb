"""GTK4/libadwaita application entry point."""

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk

from .window import MainWindow


class G915XApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.g915x.rgb",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(self)
        win.present()


def main():
    app = G915XApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
