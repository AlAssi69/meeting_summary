import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts

ColumnLayout {
    id: root
    property string mapMessageId: ""
    property string keysPayload: ""

    spacing: 10

    Label {
        text: qsTr("Diarization complete — name each speaker, then confirm to generate the summary.")
        wrapMode: Text.Wrap
        Layout.fillWidth: true
        font.pixelSize: 12
        font.bold: true
        color: app.themeController.textPrimary
    }

    ListModel {
        id: speakerModel
    }

    function reloadKeys() {
        speakerModel.clear()
        try {
            var o = JSON.parse(keysPayload || "{}")
            var keys = o.keys || []
            for (var i = 0; i < keys.length; ++i) {
                var k = String(keys[i])
                speakerModel.append({"key": k, "name": k})
            }
        } catch (e) {
            speakerModel.clear()
        }
    }

    onKeysPayloadChanged: reloadKeys()
    Component.onCompleted: reloadKeys()

    Repeater {
        model: speakerModel
        delegate: RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                id: playSampleBtn
                text: qsTr("▶ ")
                visible: app.chatController.speakerSamplePlaybackAvailable
                         && app.chatController.speakerSampleAudioPath.length > 0
                enabled: !app.chatController.busy
                implicitWidth: 36
                topPadding: 4
                bottomPadding: 4
                leftPadding: 6
                rightPadding: 6
                background: Rectangle {
                    anchors.fill: parent
                    radius: 6
                    property color base: app.themeController.accent
                    color: !playSampleBtn.enabled ? app.themeController.borderColor : (playSampleBtn.pressed ? Qt.darker(base, 1.15) : (playSampleBtn.hovered ? Qt.lighter(base, 1.06) : base))
                }
                contentItem: Label {
                    text: playSampleBtn.text
                    font.bold: true
                    color: app.themeController.onAccentText
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: app.chatController.playSpeakerVoiceSample(model.key)
            }
            Label {
                text: model.key
                Layout.preferredWidth: 110
                font.pixelSize: 12
                color: app.themeController.textPrimary
            }
            Basic.TextField {
                Layout.fillWidth: true
                text: model.name
                placeholderText: qsTr("Display name")
                placeholderTextColor: app.themeController.textMuted
                selectByMouse: true
                color: app.themeController.textPrimary
                font.pixelSize: 12
                background: Rectangle {
                    color: app.themeController.inputSurface
                    radius: 6
                    border.color: app.themeController.borderColor
                    border.width: 1
                }
                onEditingFinished: speakerModel.setProperty(index, "name", text)
            }
        }
    }

    RowLayout {
        spacing: 8
        Button {
            id: confirmSpeakerBtn
            text: qsTr("Confirm and generate summary")
            enabled: !app.chatController.busy
            topPadding: 8
            bottomPadding: 8
            leftPadding: 16
            rightPadding: 16
            background: Rectangle {
                anchors.fill: parent
                radius: 8
                property color base: app.themeController.accent
                color: !confirmSpeakerBtn.enabled ? app.themeController.borderColor : (confirmSpeakerBtn.pressed ? Qt.darker(base, 1.15) : (confirmSpeakerBtn.hovered ? Qt.lighter(base, 1.06) : base))
            }
            contentItem: Label {
                text: confirmSpeakerBtn.text
                font.bold: true
                color: app.themeController.onAccentText
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            onClicked: {
                var m = {}
                for (var i = 0; i < speakerModel.count; ++i) {
                    var row = speakerModel.get(i)
                    var k = row.key
                    var n = (row.name || "").trim()
                    m[k] = n.length ? n : k
                }
                app.chatController.confirmSpeakerNames(mapMessageId, JSON.stringify(m))
            }
        }
        Button {
            id: defaultLabelsBtn
            text: qsTr("Use default labels")
            flat: true
            enabled: !app.chatController.busy
            contentItem: Label {
                text: defaultLabelsBtn.text
                font: defaultLabelsBtn.font
                color: app.themeController.accent
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                anchors.fill: parent
                radius: 4
                color: defaultLabelsBtn.hovered ? app.themeController.linkHoverBackground : "transparent"
            }
            onClicked: {
                var m = {}
                for (var i = 0; i < speakerModel.count; ++i) {
                    var row = speakerModel.get(i)
                    m[row.key] = row.key
                }
                app.chatController.confirmSpeakerNames(mapMessageId, JSON.stringify(m))
            }
        }
        Button {
            id: cancelSpeakerBtn
            text: qsTr("Cancel")
            flat: true
            enabled: !app.chatController.busy
            contentItem: Label {
                text: cancelSpeakerBtn.text
                font: cancelSpeakerBtn.font
                color: app.themeController.accent
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                anchors.fill: parent
                radius: 4
                color: cancelSpeakerBtn.hovered ? app.themeController.linkHoverBackground : "transparent"
            }
            onClicked: app.chatController.cancelSpeakerMapping(mapMessageId)
        }
    }
}
