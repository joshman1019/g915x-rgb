"""Asynchronous D-Bus link from the interface to the service."""

from __future__ import annotations

import json
import logging

from PySide6.QtCore import SLOT, QObject, Signal, Slot
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher

logger = logging.getLogger("g915x.proxy")

NAME = "org.g915xrgb.Controller"
PATH = "/org/g915xrgb/Controller"


class DaemonProxy(QObject):
    """No call blocks the interface; D-Bus starts the service on demand."""

    status = Signal(dict)
    switched = Signal(str, str)
    windowPicked = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bus = QDBusConnection.sessionBus()
        self._watchers: set = set()

    def start(self) -> None:
        self._bus.connect(NAME, PATH, NAME, "StatusChanged", self, SLOT("_status(QString)"))
        self._bus.connect(NAME, PATH, NAME, "ProfileSwitched", self,
                          SLOT("_switched(QString,QString)"))
        self._call("GetStatus", done=lambda r: self._status(r[0]))

    def _call(self, method: str, *args, done=None, target=(NAME, PATH, NAME), timeout=-1) -> None:
        msg = QDBusMessage.createMethodCall(*target, method)
        msg.setArguments(list(args))
        watcher = QDBusPendingCallWatcher(self._bus.asyncCall(msg, timeout))
        self._watchers.add(watcher)

        def finished(w) -> None:
            self._watchers.discard(watcher)
            reply = w.reply()
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                logger.info("%s: %s", method, reply.errorMessage())
                if target[0] == NAME:
                    self.status.emit({"error": reply.errorMessage()})
            elif done is not None:
                done(reply.arguments())

        watcher.finished.connect(finished)

    @Slot(str)
    def _status(self, text: str) -> None:
        try:
            self.status.emit(json.loads(text))
        except ValueError:
            logger.warning("unreadable status")

    @Slot(str, str)
    def _switched(self, name: str, reason: str) -> None:
        self.switched.emit(name, reason)

    def apply(self, name: str, transition: str = "") -> None:
        self._call("ReloadProfiles", done=lambda _r: self._call("SetProfile", name, transition))

    def preview(self, payload: str) -> None:
        self._call("PreviewProfile", payload)

    def stop_preview(self) -> None:
        self._bus.send(QDBusMessage.createMethodCall(NAME, PATH, NAME, "StopPreview"))

    def reload_rules(self) -> None:
        self._call("ReloadRules")

    def reload_gkey_actions(self) -> None:
        self._call("ReloadGKeyActions")

    def set_option(self, name: str, value_json: str) -> None:
        self._call("SetOption", name, value_json)

    def pick_window(self) -> None:
        def done(reply) -> None:
            if reply and reply[0]:
                self.windowPicked.emit(str(reply[0]))
        # The service asks KWin: PySide6 cannot unpack KWin's a{sv} reply.
        # Waits for the person to click a window.
        self._call("PickWindow", done=done, timeout=120_000)
