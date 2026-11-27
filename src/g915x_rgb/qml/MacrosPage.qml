pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: root
    required property var editor

    title: qsTr("G-key macros")

    ColumnLayout {
        width: parent.width
        spacing: Kirigami.Units.largeSpacing

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Assign an action to each G key. Profile switching is supported in this first version.")
        }

        Repeater {
            model: editor.profile.gkeys

            delegate: RowLayout {
                required property var modelData

                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing

                        Kirigami.InlineMessage {
                            Layout.fillWidth: true
                            visible: root.editor.status.typing_available === false
                            type: Kirigami.MessageType.Warning
                            text: qsTr("The service cannot read this keyboard's key presses, so
        typing effects will not appear. See /usr/share/doc/g915x-rgb for how to allow it.")
                        }

                QQC2.Label {
                    Layout.preferredWidth: 50
                    text: modelData.name
                }

                QQC2.ComboBox {
                    id: actionBox
                    Layout.preferredWidth: 180
                    model: [
                        { text: qsTr("No action"), value: "" },
                        { text: qsTr("Switch profile"), value: "switch_profile" }
                    ]
                    textRole: "text"
                    valueRole: "value"
                    Component.onCompleted: {
                        currentIndex = Math.max(0, indexOfValue(modelData.type));
                    }

                    onActivated: {
                        const target = targetBox.currentText;
                        editor.setGKeyAction(modelData.address, currentValue, target);
                    }
                }

                QQC2.ComboBox {
                    id: targetBox
                    Layout.fillWidth: true
                    model: editor.profiles.map(profile => profile.name)
                    enabled: actionBox.currentValue === "switch_profile"
                    currentIndex: Math.max(0, model.indexOf(modelData.target))

                    onActivated: {
                        editor.setGKeyAction(
                            modelData.address,
                            actionBox.currentValue,
                            currentText
                        );
                    }
                }
            }
        }
    }
}
