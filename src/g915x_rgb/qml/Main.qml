pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: window

    required property var editor
    readonly property var pages: ["colors", "effects", "typing", "macros", "rules", "device"]
    property int page: 0
    property bool closing: false

    title: editor.profile.name
    width: Kirigami.Units.gridUnit * 64
    height: Kirigami.Units.gridUnit * 43
    minimumWidth: Kirigami.Units.gridUnit * 36
    minimumHeight: Kirigami.Units.gridUnit * 28
    onPageChanged: editor.setPage(pages[page])

    onClosing: event => {
        if (editor.anyDirty && !closing) {
            event.accepted = false;
            closeDialog.open();
        }
    }

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar
    pageStack.initialPage: Kirigami.Page {
        title: window.editor.profile.dirty ? qsTr("%1 (unsaved)").arg(window.editor.profile.name) : window.editor.profile.name
        padding: 0
        actions: [
            Kirigami.Action { text: qsTr("Undo"); icon.name: "edit-undo"; shortcut: StandardKey.Undo; enabled: window.editor.profile.canUndo; onTriggered: window.editor.undo() },
            Kirigami.Action { text: qsTr("Redo"); icon.name: "edit-redo"; shortcut: StandardKey.Redo; enabled: window.editor.profile.canRedo; onTriggered: window.editor.redo() },
            Kirigami.Action { text: qsTr("Save"); icon.name: "document-save"; shortcut: StandardKey.Save; enabled: window.editor.profile.dirty; onTriggered: window.editor.save() }
        ]

        RowLayout {
            anchors.fill: parent
            spacing: 0

            Rectangle {
                Layout.fillHeight: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 11
                Kirigami.Theme.colorSet: Kirigami.Theme.View
                Kirigami.Theme.inherit: false
                color: Kirigami.Theme.backgroundColor

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    RowLayout {
                        Layout.margins: Kirigami.Units.smallSpacing
                        Kirigami.Heading { Layout.fillWidth: true; Layout.leftMargin: Kirigami.Units.smallSpacing; level: 4; text: qsTr("Profiles") }
                        QQC2.ToolButton { icon.name: "list-add"; Accessible.name: qsTr("New profile"); onClicked: window.editor.addProfile() }
                        QQC2.ToolButton { icon.name: "edit-rename"; Accessible.name: qsTr("Rename profile"); onClicked: renameDialog.open() }
                        QQC2.ToolButton { icon.name: "edit-delete"; Accessible.name: qsTr("Delete profile"); enabled: window.editor.profiles.length > 1; onClicked: deleteDialog.open() }
                    }
                    QQC2.ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        ListView {
                            model: window.editor.profiles
                            delegate: QQC2.ItemDelegate {
                                id: row
                                required property var modelData
                                required property int index
                                width: ListView.view.width
                                highlighted: index === window.editor.profile.index
                                Accessible.name: modelData.name
                                onClicked: window.editor.selectProfile(index)
                                contentItem: ColumnLayout {
                                    QQC2.Label {
                                        Layout.fillWidth: true
                                        text: row.modelData.dirty ? row.modelData.name + " *" : row.modelData.name
                                        textFormat: Text.PlainText
                                        elide: Text.ElideRight
                                    }
                                    Row {
                                        Layout.fillWidth: true
                                        Repeater {
                                            model: row.modelData.strip
                                            delegate: Rectangle {
                                                required property var modelData
                                                width: (row.width - row.leftPadding - row.rightPadding) / row.modelData.strip.length
                                                height: 4
                                                color: modelData
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    QQC2.Label {
                        Layout.margins: Kirigami.Units.largeSpacing
                        color: Kirigami.Theme.disabledTextColor
                        text: {
                            const s = window.editor.status;
                            if (!s.connected)
                                return qsTr("Keyboard not connected");
                            return s.battery_percent >= 0 ? qsTr("Connected\nBattery %1%").arg(s.battery_percent) : qsTr("Connected");
                        }
                    }
                }
            }
            Kirigami.Separator { Layout.fillHeight: true }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                QQC2.TabBar {
                    Layout.fillWidth: true
                    currentIndex: window.page
                    onCurrentIndexChanged: window.page = currentIndex
                    QQC2.TabButton { text: qsTr("Colors"); icon.name: "color-management" }
                    QQC2.TabButton { text: qsTr("Effects"); icon.name: "media-playback-start" }
                    QQC2.TabButton { text: qsTr("Typing"); icon.name: "input-keyboard" }
                    QQC2.TabButton { text: qsTr("Macros"); icon.name: "configure-shortcuts" }
                    QQC2.TabButton { text: qsTr("App rules"); icon.name: "preferences-system-windows" }
                    QQC2.TabButton { text: qsTr("Device"); icon.name: "configure" }
                }
                KeyboardView {
                    editor: window.editor
                    visible: window.page < 3
                    showSelection: window.page === 0
                    Layout.fillWidth: true
                    Layout.margins: Kirigami.Units.largeSpacing
                    Layout.maximumHeight: window.height * 0.5
                    Layout.preferredHeight: implicitHeight
                }
                Kirigami.Separator { Layout.fillWidth: true; visible: window.page < 3 }
                QQC2.ScrollView {
                    id: scroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentWidth: availableWidth
                    leftPadding: Kirigami.Units.gridUnit
                    rightPadding: Kirigami.Units.gridUnit
                    topPadding: Kirigami.Units.largeSpacing
                    bottomPadding: Kirigami.Units.largeSpacing

                    Loader {
                        width: scroll.availableWidth
                        sourceComponent: [colorsPage, effectsPage, typingPage, macrosPage, rulesPage, devicePage][window.page]
                    }
                }
            }
        }
    }

    Component { id: colorsPage; ColorsPage { editor: window.editor } }
    Component { id: effectsPage; EffectsPage { editor: window.editor } }
    Component { id: typingPage; TypingPage { editor: window.editor } }
    Component { id: macrosPage; MacrosPage { editor: window.editor } }
    Component { id: rulesPage; RulesPage { editor: window.editor } }
    Component { id: devicePage; DevicePage { editor: window.editor } }

    Kirigami.PromptDialog {
        id: renameDialog
        title: qsTr("Rename profile")
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onOpened: {
            nameField.text = window.editor.profile.name;
            nameField.selectAll();
            nameField.forceActiveFocus();
        }
        onAccepted: window.editor.renameProfile(nameField.text)
        QQC2.TextField {
            id: nameField
            maximumLength: 60
            Accessible.name: qsTr("Profile name")
            onAccepted: renameDialog.accept()
        }
    }
    Kirigami.PromptDialog {
        id: deleteDialog
        title: qsTr("Delete profile")
        subtitle: qsTr("Delete “%1”? This cannot be undone.").arg(window.editor.profile.name)
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: window.editor.deleteProfile()
    }
    Kirigami.PromptDialog {
        id: closeDialog
        title: qsTr("Unsaved changes")
        subtitle: qsTr("Save your changes before closing?")
        standardButtons: Kirigami.Dialog.Save | Kirigami.Dialog.Discard | Kirigami.Dialog.Cancel
        onAccepted: if (window.editor.saveAll()) { window.closing = true; window.close(); }
        onDiscarded: { window.closing = true; window.close(); }
    }

    Connections {
        target: window.editor
        function onMessage(text) { window.showPassiveNotification(text, "long"); }
    }
}
