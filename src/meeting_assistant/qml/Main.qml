import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// Explicit Basic controls where we customize `background` (safe if env style differs).
import QtQuick.Controls.Basic as Basic
import MeetingAssistant 1.0

ApplicationWindow {
    id: win
    width: 1000
    height: 640
    minimumWidth: 720
    minimumHeight: 480
    visible: true
    title: qsTr("🎙️ Meeting Assistant")
    color: app.themeController.windowBackground

    readonly property bool pipelineStartLocked: app.chatController.pipelineStartLocked
    readonly property bool stagingImportLocked: app.chatController.stagingImportLocked
    readonly property bool recordingLocked: app.chatController.recordingLocked

    readonly property var ltrIsolate: function (s) {
        return "\u200E" + s + "\u200E"
    }

    // QML url values do not expose toLocalFile() as a callable — normalize via string (Windows-safe).
    readonly property var urlToLocalPath: function (u) {
        if (u === undefined || u === null)
            return ""
        var s = typeof u === "string" ? u : (u.toString !== undefined ? u.toString() : String(u))
        if (s.indexOf("file:") !== 0)
            return s
        s = s.replace(/^file:\/+/, "")
        if (Qt.platform.os === "windows") {
            if (s.length >= 3 && s.charAt(0) === "/" && s.charAt(2) === ":")
                s = s.substring(1)
        }
        try {
            return decodeURIComponent(s)
        } catch (e) {
            return s
        }
    }

    function openSendPromptDialog() {
        if (!app.chatController.sendPendingAudioValidated())
            return
        promptRunDialog.pendingAction = "send"
        promptRunDialog.modeFull = true
        promptRunDialog.promptLlmDraft = app.chatController.defaultSendPromptLlm()
        promptRunDialog.promptWhisperDraft = app.chatController.defaultSendPromptWhisper()
        promptRunDialog.open()
    }

    function openReprocessPromptDialog(filePath) {
        if (!app.chatController.reprocessAudioValidated(filePath))
            return
        var d = app.chatController.reprocessPromptDefaults(filePath)
        promptRunDialog.pendingAction = "reprocess"
        promptRunDialog.pendingReprocessPath = filePath
        promptRunDialog.modeFull = true
        promptRunDialog.promptLlmDraft = d.llm
        promptRunDialog.promptWhisperDraft = d.whisper
        promptRunDialog.open()
    }

    function openSummarizeAgainDialog(messageId) {
        if (!app.chatController.summarizeAgainValidated(messageId))
            return
        promptRunDialog.pendingAction = "summarize"
        promptRunDialog.pendingSummarizeMessageId = messageId
        promptRunDialog.modeFull = false
        promptRunDialog.promptLlmDraft = app.chatController.summarizeAgainLlmDefault(messageId)
        promptRunDialog.promptWhisperDraft = ""
        promptRunDialog.open()
    }

    FileDialog {
        id: audioImportDialog
        title: qsTr("Import audio file")
        nameFilters: app.chatController.audioImportNameFilters
        onAccepted: {
            app.chatController.stageAudioFile(win.urlToLocalPath(audioImportDialog.selectedFile))
        }
    }

    Dialog {
        id: promptRunDialog
        property bool modeFull: true
        property string pendingAction: ""
        property string pendingReprocessPath: ""
        property string pendingSummarizeMessageId: ""
        property string promptLlmDraft: ""
        property string promptWhisperDraft: ""
        title: modeFull ? qsTr("Prompts before run") : qsTr("Summarization prompt")
        modal: true
        anchors.centerIn: parent
        width: Math.min(520, win.width - 32)
        onOpened: {
            promptLlmArea.text = promptLlmDraft
            promptWhisperArea.text = promptWhisperDraft
            promptLlmArea.forceActiveFocus()
        }

        ColumnLayout {
            id: contentColumn
            width: Math.min(472, win.width - 48)
            spacing: 10
            Label {
                text: qsTr("Gemma (summarization instructions)")
                color: app.themeController.textMuted
                font.pixelSize: 12
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: promptRunDialog.modeFull ? 110 : 140
                clip: true
                Basic.TextArea {
                    id: promptLlmArea
                    wrapMode: TextArea.Wrap
                    color: app.themeController.textPrimary
                    background: Rectangle {
                        color: app.themeController.inputSurface
                        radius: 6
                        border.color: app.themeController.borderColor
                        border.width: 1
                    }
                }
            }
            Label {
                visible: promptRunDialog.modeFull
                text: qsTr("Whisper (transcription context / initial prompt)")
                color: app.themeController.textMuted
                font.pixelSize: 12
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            ScrollView {
                visible: promptRunDialog.modeFull
                Layout.fillWidth: true
                Layout.preferredHeight: 110
                clip: true
                Basic.TextArea {
                    id: promptWhisperArea
                    wrapMode: TextArea.Wrap
                    placeholderText: qsTr("Tip: Arabic context plus exact English terms to preserve (e.g. Kalman filter, REST API, Docker).")
                    color: app.themeController.textPrimary
                    background: Rectangle {
                        color: app.themeController.inputSurface
                        radius: 6
                        border.color: app.themeController.borderColor
                        border.width: 1
                    }
                }
            }
            Item {
                Layout.preferredHeight: 8
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Item {
                    Layout.fillWidth: true
                }
                ChromeButton {
                    text: qsTr("Cancel")
                    onClicked: promptRunDialog.close()
                }
                Button {
                    id: promptRunConfirmBtn
                    text: {
                        if (promptRunDialog.pendingAction === "send")
                            return qsTr("Send")
                        if (promptRunDialog.pendingAction === "summarize")
                            return qsTr("Summarize")
                        return qsTr("Re-transcribe")
                    }
                    topPadding: 8
                    bottomPadding: 8
                    leftPadding: 16
                    rightPadding: 16
                    background: Rectangle {
                        anchors.fill: parent
                        radius: 8
                        property color base: app.themeController.accent
                        color: promptRunConfirmBtn.pressed ? Qt.darker(base, 1.15) : (promptRunConfirmBtn.hovered ? Qt.lighter(base, 1.06) : base)
                    }
                    contentItem: Label {
                        text: promptRunConfirmBtn.text
                        font.bold: true
                        color: app.themeController.onAccentText
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        var llm = promptLlmArea.text
                        var wh = promptRunDialog.modeFull ? promptWhisperArea.text : ""
                        if (promptRunDialog.pendingAction === "send")
                            app.chatController.commitSendPendingAudio(llm, wh)
                        else if (promptRunDialog.pendingAction === "reprocess")
                            app.chatController.commitReprocessAudio(promptRunDialog.pendingReprocessPath, llm, wh)
                        else if (promptRunDialog.pendingAction === "summarize")
                            app.chatController.commitSummarizeAgain(promptRunDialog.pendingSummarizeMessageId, llm)
                        promptRunDialog.close()
                    }
                }
            }
        }
    }

    header: ToolBar {
        topPadding: 10
        bottomPadding: 10
        leftPadding: 0
        rightPadding: 0
        background: Rectangle { color: app.themeController.surface }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 12
            Label {
                Layout.alignment: Qt.AlignVCenter
                text: qsTr("🗂️ Local AI Meeting Assistant")
                color: app.themeController.textPrimary
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            ColumnLayout {
                id: hdrStatusBlock
                visible: app.chatController.busy || app.chatController.statusText.length > 0
                spacing: 3
                Layout.maximumWidth: Math.max(220, Math.min(520, win.width - 420))
                Layout.alignment: Qt.AlignVCenter
                Label {
                    text: qsTr("Status")
                    color: app.themeController.textMuted
                    font.pixelSize: 10
                    font.bold: true
                    font.capitalization: Font.AllUppercase
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignLeft
                }
                Label {
                    id: hdrStatusMessage
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignLeft
                    wrapMode: Text.Wrap
                    text: {
                        if (app.chatController.busy) {
                            if (app.chatController.currentPhase === "summarizing")
                                return qsTr("Generating summary with the local model…")
                            if (app.chatController.currentPhase === "transcribing")
                                return qsTr("Transcribing audio with WhisperX…")
                            return qsTr("Working…")
                        }
                        return app.chatController.statusText
                    }
                    color: app.themeController.textPrimary
                    font.pixelSize: 12
                }
            }
            BusyIndicator {
                Layout.alignment: Qt.AlignVCenter
                running: app.chatController.busy
                implicitWidth: 28
                implicitHeight: 28
                palette.text: app.themeController.textPrimary
            }
            Label {
                visible: app.chatController.busy
                Layout.alignment: Qt.AlignVCenter
                text: win.ltrIsolate(app.chatController.processingElapsedText)
                color: app.themeController.textPrimary
                font.pixelSize: 13
                font.bold: true
            }
            Button {
                id: hdrStopProcessingBtn
                visible: app.chatController.busy
                Layout.alignment: Qt.AlignVCenter
                text: qsTr("Stop")
                topPadding: 6
                bottomPadding: 6
                leftPadding: 12
                rightPadding: 12
                onClicked: stopProcessingDialog.open()
                contentItem: Label {
                    text: hdrStopProcessingBtn.text
                    font {
                        family: hdrStopProcessingBtn.font.family
                        pixelSize: hdrStopProcessingBtn.font.pixelSize
                        bold: true
                    }
                    color: app.themeController.onAccentText
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    anchors.fill: parent
                    radius: 6
                    color: hdrStopProcessingBtn.pressed
                           ? "#b91c1c"
                           : (hdrStopProcessingBtn.hovered ? "#f87171" : "#dc2626")
                    border.width: 0
                }
            }
            Button {
                id: hdrThemeBtn
                Layout.alignment: Qt.AlignVCenter
                text: app.themeController.darkMode ? qsTr("☀️ Light") : qsTr("🌙 Dark")
                topPadding: 6
                bottomPadding: 6
                leftPadding: 12
                rightPadding: 12
                background: Rectangle {
                    anchors.fill: parent
                    radius: 6
                    color: hdrThemeBtn.pressed ? app.themeController.chromePressed : (hdrThemeBtn.hovered ? app.themeController.chromeHover : app.themeController.headerChromeFill)
                    border.width: app.themeController.darkMode ? 0 : 1
                    border.color: app.themeController.borderColor
                }
                contentItem: Label {
                    text: hdrThemeBtn.text
                    font: hdrThemeBtn.font
                    color: app.themeController.textPrimary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: app.themeController.toggleDarkMode()
            }
            Button {
                id: hdrLangBtn
                Layout.alignment: Qt.AlignVCenter
                text: app.localeController.language === "ar" ? qsTr("English") : qsTr("العربية")
                topPadding: 6
                bottomPadding: 6
                leftPadding: 12
                rightPadding: 12
                background: Rectangle {
                    anchors.fill: parent
                    radius: 6
                    color: hdrLangBtn.pressed ? app.themeController.chromePressed : (hdrLangBtn.hovered ? app.themeController.chromeHover : app.themeController.headerChromeFill)
                    border.width: app.themeController.darkMode ? 0 : 1
                    border.color: app.themeController.borderColor
                }
                contentItem: Label {
                    text: hdrLangBtn.text
                    font: hdrLangBtn.font
                    color: app.themeController.textPrimary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: app.localeController.setLanguage(app.localeController.language === "ar" ? "en" : "ar")
            }
            Button {
                id: hdrSettingsBtn
                Layout.alignment: Qt.AlignVCenter
                text: qsTr("⚙️ Settings")
                topPadding: 6
                bottomPadding: 6
                leftPadding: 12
                rightPadding: 12
                background: Rectangle {
                    anchors.fill: parent
                    radius: 6
                    color: hdrSettingsBtn.pressed ? app.themeController.chromePressed : (hdrSettingsBtn.hovered ? app.themeController.chromeHover : app.themeController.headerChromeFill)
                    border.width: app.themeController.darkMode ? 0 : 1
                    border.color: app.themeController.borderColor
                }
                contentItem: Label {
                    text: hdrSettingsBtn.text
                    font: hdrSettingsBtn.font
                    color: app.themeController.textPrimary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: settingsPopup.open()
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 260
            Layout.fillHeight: true
            color: app.themeController.surface
            border.width: 0

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8
                Button {
                    id: newSessionBtn
                    text: qsTr("➕ New session")
                    Layout.fillWidth: true
                    topPadding: 10
                    bottomPadding: 10
                    leftPadding: 14
                    rightPadding: 14
                    background: Rectangle {
                        anchors.fill: parent
                        radius: 8
                        property color base: app.themeController.accent
                        color: newSessionBtn.pressed ? Qt.darker(base, 1.15) : (newSessionBtn.hovered ? Qt.lighter(base, 1.06) : base)
                    }
                    contentItem: Label {
                        text: newSessionBtn.text
                        font.bold: true
                        color: app.themeController.onAccentText
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: app.sessionController.newSession()
                }
                Label {
                    text: qsTr("📋 Sessions")
                    color: app.themeController.textMuted
                    font.pixelSize: 12
                }
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    ListView {
                        id: sessionList
                        anchors.fill: parent
                        spacing: 4
                        model: app.sessionController.sessions
                        delegate: Rectangle {
                            required property var modelData
                            width: sessionList.width
                            height: 44
                            radius: 6
                            color: titleMouse.containsMouse ? app.themeController.sessionListHover : "transparent"
                            border.width: modelData.id === app.sessionController.currentSessionId ? 1 : 0
                            border.color: app.themeController.accent

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 4
                                Item {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Label {
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        text: modelData.title
                                        elide: Text.ElideRight
                                        color: app.themeController.textPrimary
                                    }
                                    MouseArea {
                                        id: titleMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        onClicked: app.sessionController.selectSession(modelData.id)
                                    }
                                }
                                ChromeButton {
                                    flatLink: true
                                    text: qsTr("Rename")
                                    onClicked: {
                                        renameSessionDialog.pendingSessionId = modelData.id
                                        renameSessionDialog.draftTitle = modelData.title
                                        renameSessionDialog.open()
                                    }
                                }
                                ChromeButton {
                                    flatLink: true
                                    dangerLink: true
                                    text: qsTr("Delete…")
                                    enabled: !win.pipelineStartLocked
                                    onClicked: {
                                        deleteSessionDialog.pendingSessionId = modelData.id
                                        deleteSessionDialog.pendingTitle = modelData.title
                                        deleteSessionDialog.open()
                                    }
                                }
                            }
                        }
                    }
                }
            }
            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: app.themeController.borderColor
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            DropArea {
                id: chatDropArea
                anchors.fill: parent
                keys: ["text/uri-list"]

                Rectangle {
                    anchors.fill: parent
                    z: -1
                    color: "transparent"
                    border.width: chatDropArea.containsDrag ? 2 : 0
                    border.color: app.themeController.accent
                }

                onDropped: function (drop) {
                    if (!drop.hasUrls)
                        return
                    var paths = []
                    for (var i = 0; i < drop.urls.length; i++)
                        paths.push(win.urlToLocalPath(drop.urls[i]))
                    app.chatController.stageDroppedLocalPaths(paths)
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    Label {
                        anchors.centerIn: parent
                        width: Math.min(420, parent.width - 48)
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        visible: app.chatController.messages.length === 0
                        text: qsTr("No messages yet.\n📎 Drop an audio file here, use 📂 Import, or use 🎤 Record to capture your microphone.")
                        color: app.themeController.textMuted
                        font.pixelSize: 13
                    }

                    ScrollView {
                        anchors.fill: parent
                        visible: app.chatController.messages.length > 0
                        background: Rectangle { color: win.color }
                        clip: true
                        ListView {
                            id: msgList
                            anchors.fill: parent
                            topMargin: 12
                            bottomMargin: 12
                            leftMargin: 12
                            rightMargin: 12
                            spacing: 10
                            model: app.chatController.messages

                            footer: Item {
                                width: msgList.width
                                height: app.chatController.busy ? (pipelineCard.height + 12) : 0

                                Rectangle {
                                    id: pipelineCard
                                    visible: app.chatController.busy
                                    width: parent.width - 24
                                    x: 12
                                    height: pipelineRoot.implicitHeight + 16
                                    radius: 10
                                    color: app.themeController.surface
                                    border.width: 1
                                    border.color: app.themeController.borderColor

                                    ColumnLayout {
                                        id: pipelineRoot
                                        width: parent.width - 20
                                        anchors.centerIn: parent
                                        spacing: 8
                                        RowLayout {
                                            id: pipelineRow
                                            Layout.fillWidth: true
                                            spacing: 12
                                            BusyIndicator {
                                                running: app.chatController.busy
                                                implicitWidth: 32
                                                implicitHeight: 32
                                                palette.text: app.themeController.textPrimary
                                            }
                                            Label {
                                                visible: app.chatController.busy
                                                Layout.alignment: Qt.AlignVCenter
                                                text: win.ltrIsolate(app.chatController.processingElapsedText)
                                                color: app.themeController.textPrimary
                                                font.pixelSize: 13
                                                font.bold: true
                                            }
                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 2
                                                Label {
                                                    text: {
                                                        if (app.chatController.currentPhase === "summarizing")
                                                            return qsTr("Generating summary with local LLM…")
                                                        return qsTr("Transcribing with WhisperX…")
                                                    }
                                                    color: app.themeController.textPrimary
                                                    font.pixelSize: 13
                                                    font.bold: true
                                                    wrapMode: Text.Wrap
                                                    Layout.fillWidth: true
                                                }
                                                Label {
                                                    text: app.modelStatusController.modelSummary
                                                    color: app.themeController.textMuted
                                                    font.pixelSize: 11
                                                    wrapMode: Text.Wrap
                                                    Layout.fillWidth: true
                                                }
                                            }
                                            Button {
                                                id: pipelineStopBtn
                                                visible: app.chatController.busy
                                                Layout.alignment: Qt.AlignVCenter
                                                text: qsTr("Stop")
                                                topPadding: 6
                                                bottomPadding: 6
                                                leftPadding: 14
                                                rightPadding: 14
                                                onClicked: stopProcessingDialog.open()
                                                contentItem: Label {
                                                    text: pipelineStopBtn.text
                                                    font {
                                                        family: pipelineStopBtn.font.family
                                                        pixelSize: pipelineStopBtn.font.pixelSize
                                                        bold: true
                                                    }
                                                    color: app.themeController.onAccentText
                                                    horizontalAlignment: Text.AlignHCenter
                                                    verticalAlignment: Text.AlignVCenter
                                                }
                                                background: Rectangle {
                                                    anchors.fill: parent
                                                    radius: 6
                                                    color: pipelineStopBtn.pressed
                                                           ? "#b91c1c"
                                                           : (pipelineStopBtn.hovered ? "#f87171" : "#dc2626")
                                                    border.width: 0
                                                }
                                            }
                                        }
                                        ColumnLayout {
                                            visible: app.chatController.currentPhase === "transcribing" && app.chatController.sttPipelineLog.length > 0
                                            Layout.fillWidth: true
                                            spacing: 4
                                            Repeater {
                                                model: app.chatController.sttPipelineLog
                                                delegate: Rectangle {
                                                    required property var modelData
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: sttLine.implicitHeight + 10
                                                    radius: 6
                                                    color: modelData.kind === "warning" ? app.themeController.warningBannerBackground : (modelData.kind === "error" ? app.themeController.errorBannerBackground : app.themeController.infoBannerBackground)
                                                    border.width: 1
                                                    border.color: modelData.kind === "warning" ? app.themeController.warningBannerBorder : (modelData.kind === "error" ? app.themeController.errorBannerBorder : app.themeController.infoBannerBorder)
                                                    Label {
                                                        id: sttLine
                                                        anchors.fill: parent
                                                        anchors.margins: 6
                                                        wrapMode: Text.Wrap
                                                        text: modelData.message
                                                        font.pixelSize: 11
                                                        color: app.themeController.textPrimary
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            delegate: ColumnLayout {
                                required property var modelData
                                readonly property string sysKind: {
                                    if (modelData.role !== "system")
                                        return ""
                                    var k = modelData.systemKind
                                    if (k === "error" || k === "warning" || k === "info")
                                        return k
                                    return "error"
                                }
                                width: msgList.width - msgList.leftMargin - msgList.rightMargin
                                spacing: 4

                                Rectangle {
                                    Layout.maximumWidth: Math.min(720, msgList.width - msgList.leftMargin - msgList.rightMargin - 24)
                                    Layout.alignment: modelData.role === "user"
                                        ? (Qt.application.layoutDirection === Qt.RightToLeft ? Qt.AlignLeft : Qt.AlignRight)
                                        : (Qt.application.layoutDirection === Qt.RightToLeft ? Qt.AlignRight : Qt.AlignLeft)
                                    implicitWidth: Math.min(720, msgList.width - msgList.leftMargin - msgList.rightMargin - 24)
                                    implicitHeight: innerCol.implicitHeight + 24
                                    radius: 10
                                    color: {
                                        if (modelData.role === "system") {
                                            if (sysKind === "warning")
                                                return app.themeController.warningBannerBackground
                                            if (sysKind === "info")
                                                return app.themeController.infoBannerBackground
                                            return app.themeController.errorBannerBackground
                                        }
                                        if (modelData.role === "user")
                                            return app.themeController.userBubble
                                        if (modelData.role === "assistant") {
                                            if (modelData.assistantKind === "transcript")
                                                return app.themeController.transcriptCardBackground
                                            if (modelData.assistantKind === "summary")
                                                return app.themeController.summaryCardBackground
                                            if (modelData.assistantKind === "speaker_map")
                                                return app.themeController.surface
                                        }
                                        return app.themeController.assistantBubble
                                    }
                                    border.color: {
                                        if (modelData.role === "system") {
                                            if (sysKind === "warning")
                                                return app.themeController.warningBannerBorder
                                            if (sysKind === "info")
                                                return app.themeController.infoBannerBorder
                                            return app.themeController.errorBannerBorder
                                        }
                                        if (modelData.role === "assistant") {
                                            if (modelData.assistantKind === "transcript")
                                                return app.themeController.transcriptCardBorder
                                            if (modelData.assistantKind === "summary")
                                                return app.themeController.summaryCardBorder
                                            if (modelData.assistantKind === "speaker_map")
                                                return app.themeController.borderColor
                                        }
                                        return app.themeController.borderColor
                                    }
                                    border.width: 1

                                    ColumnLayout {
                                        id: innerCol
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.margins: 12
                                        spacing: 8
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 8
                                            Item { Layout.fillWidth: true }
                                            ChromeButton {
                                                flatLink: true
                                                text: qsTr("Copy")
                                                enabled: !app.chatController.busy
                                                onClicked: app.chatController.copyMessageFormatted(modelData.id)
                                            }
                                        }
                                        Label {
                                            visible: modelData.role !== "user"
                                            text: {
                                                if (modelData.role === "assistant") {
                                                    if (modelData.assistantKind === "transcript")
                                                        return qsTr("Transcript")
                                                    if (modelData.assistantKind === "summary")
                                                        return qsTr("Summary")
                                                    if (modelData.assistantKind === "speaker_map")
                                                        return qsTr("Speaker names")
                                                    return qsTr("Assistant")
                                                }
                                                if (modelData.role === "system") {
                                                    if (sysKind === "warning")
                                                        return qsTr("Warning")
                                                    if (sysKind === "info")
                                                        return qsTr("Info")
                                                    return qsTr("Error")
                                                }
                                                return modelData.role
                                            }
                                            font.pixelSize: 11
                                            color: {
                                                if (modelData.role === "system") {
                                                    if (sysKind === "warning")
                                                        return app.themeController.warningText
                                                    if (sysKind === "info")
                                                        return app.themeController.infoText
                                                    return app.themeController.errorText
                                                }
                                                if (modelData.role === "assistant") {
                                                    if (modelData.assistantKind === "transcript")
                                                        return app.themeController.transcriptCardTitle
                                                    if (modelData.assistantKind === "summary")
                                                        return app.themeController.summaryCardTitle
                                                    if (modelData.assistantKind === "speaker_map")
                                                        return app.themeController.textMuted
                                                }
                                                return app.themeController.textMuted
                                            }
                                        }
                                        Label {
                                            visible: modelData.role !== "user" && modelData.createdAt && modelData.createdAt.length > 0
                                            text: modelData.createdAt
                                            font.pixelSize: 10
                                            color: app.themeController.textMuted
                                        }
                                        MarkdownBody {
                                            Layout.fillWidth: true
                                            // Transcript lines must stay plain text: Qt Markdown collapses single newlines.
                                            markdownEnabled: modelData.role !== "user"
                                                              && modelData.assistantKind !== "transcript"
                                            visible: modelData.assistantKind !== "speaker_map"
                                            text: modelData.content
                                            color: app.themeController.textPrimary
                                        }
                                        SpeakerMappingCard {
                                            Layout.fillWidth: true
                                            visible: modelData.role === "assistant" && modelData.assistantKind === "speaker_map"
                                            mapMessageId: modelData.id
                                            keysPayload: modelData.content
                                        }
                                        RowLayout {
                                            visible: modelData.role === "assistant" && modelData.assistantKind === "transcript"
                                            spacing: 8
                                            ChromeButton {
                                                flatLink: true
                                                text: qsTr("📂 Open transcript file")
                                                visible: modelData.filePath && modelData.filePath.length > 0
                                                enabled: !win.pipelineStartLocked
                                                onClicked: app.chatController.openFile(modelData.filePath)
                                            }
                                            ChromeButton {
                                                flatLink: true
                                                text: qsTr("Summarize again")
                                                enabled: !win.pipelineStartLocked
                                                onClicked: win.openSummarizeAgainDialog(modelData.id)
                                            }
                                        }
                                        RowLayout {
                                            visible: modelData.role === "assistant" && modelData.assistantKind === "summary"
                                            spacing: 8
                                            ChromeButton {
                                                flatLink: true
                                                text: qsTr("📂 Open summary file")
                                                visible: modelData.filePath && modelData.filePath.length > 0
                                                enabled: !win.pipelineStartLocked
                                                onClicked: app.chatController.openFile(modelData.filePath)
                                            }
                                        }
                                        RowLayout {
                                            visible: modelData.role === "user" && modelData.filePath && modelData.filePath.length > 0
                                            spacing: 8
                                            Button {
                                                id: openFileBtn
                                                text: qsTr("📂 Open file")
                                                flat: true
                                                contentItem: Label {
                                                    text: openFileBtn.text
                                                    font: openFileBtn.font
                                                    color: app.themeController.accent
                                                    horizontalAlignment: Text.AlignHCenter
                                                    verticalAlignment: Text.AlignVCenter
                                                }
                                                background: Rectangle {
                                                    anchors.fill: parent
                                                    radius: 4
                                                    color: openFileBtn.hovered ? app.themeController.linkHoverBackground : "transparent"
                                                }
                                                onClicked: app.chatController.openFile(modelData.filePath)
                                            }
                                            ChromeButton {
                                                flatLink: true
                                                text: qsTr("Re-transcribe")
                                                enabled: !win.pipelineStartLocked
                                                onClicked: win.openReprocessPromptDialog(modelData.filePath)
                                            }
                                        }
                                        RowLayout {
                                            visible: modelData.role === "system" && modelData.filePath && modelData.filePath.length > 0 && sysKind === "error"
                                            spacing: 8
                                            ChromeButton {
                                                flatLink: true
                                                text: qsTr("Try again")
                                                enabled: !win.pipelineStartLocked
                                                onClicked: win.openReprocessPromptDialog(modelData.filePath)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: recordingBottomPanel
                    Layout.fillWidth: true
                    implicitHeight: bottomCol.implicitHeight + 28
                    color: app.themeController.surface
                    border.width: 1
                    border.color: app.themeController.borderColor

                    ColumnLayout {
                        id: bottomCol
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16
                        anchors.topMargin: 10
                        anchors.bottomMargin: 10
                        spacing: 6
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Label {
                                    text: qsTr("📎 Drop audio, Import a file, or record — press Send to set prompts and run the pipeline.")
                                    color: app.themeController.textMuted
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 11
                                }
                                Label {
                                    visible: app.chatController.pendingAudioPath.length > 0
                                    text: {
                                        var p = app.chatController.pendingAudioPath
                                        if (!p || p.length === 0)
                                            return ""
                                        var i = Math.max(p.lastIndexOf("/"), p.lastIndexOf("\\"))
                                        var name = i >= 0 ? p.substring(i + 1) : p
                                        return qsTr("Ready: %1").arg(name)
                                    }
                                    color: app.themeController.textPrimary
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 11
                                }
                                Label {
                                    visible: app.chatController.pendingAudioPath.length > 0
                                             && !win.recordingLocked
                                             && !app.chatController.recorder.recording
                                    text: qsTr("Send or clear staged audio before starting a new recording.")
                                    color: app.themeController.textMuted
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 10
                                }
                            }
                            ChromeButton {
                                flatLink: true
                                text: qsTr("Clear staged")
                                visible: app.chatController.pendingAudioPath.length > 0 && !win.stagingImportLocked
                                onClicked: app.chatController.discardPendingAudio()
                            }
                            Button {
                                id: sendBtn
                                text: qsTr("Send")
                                readonly property bool sendHasAudio: app.chatController.pendingAudioPath.length > 0
                                enabled: !win.pipelineStartLocked && !app.chatController.recorder.recording
                                opacity: sendHasAudio ? 1 : 0.55
                                topPadding: 8
                                bottomPadding: 8
                                leftPadding: 16
                                rightPadding: 16
                                background: Rectangle {
                                    anchors.fill: parent
                                    radius: 8
                                    property color base: app.themeController.accent
                                    color: !sendBtn.enabled ? app.themeController.borderColor : (sendBtn.pressed ? Qt.darker(base, 1.15) : (sendBtn.hovered ? Qt.lighter(base, 1.06) : base))
                                }
                                contentItem: Label {
                                    text: sendBtn.text
                                    font.bold: true
                                    color: app.themeController.onAccentText
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: win.openSendPromptDialog()
                            }
                            Button {
                                id: importAudioBtn
                                text: qsTr("📂 Import")
                                enabled: !win.stagingImportLocked && !app.chatController.recorder.recording
                                topPadding: 8
                                bottomPadding: 8
                                leftPadding: 16
                                rightPadding: 16
                                background: Rectangle {
                                    anchors.fill: parent
                                    radius: 8
                                    property color base: app.themeController.accent
                                    color: !importAudioBtn.enabled ? app.themeController.borderColor : (importAudioBtn.pressed ? Qt.darker(base, 1.15) : (importAudioBtn.hovered ? Qt.lighter(base, 1.06) : base))
                                }
                                contentItem: Label {
                                    text: importAudioBtn.text
                                    font.bold: true
                                    color: app.themeController.onAccentText
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: audioImportDialog.open()
                            }
                            Button {
                                id: recordBtn
                                text: app.chatController.recorder.recording ? qsTr("⏹️ Stop recording") : qsTr("🎤 Record")
                                enabled: !win.recordingLocked
                                         && (app.chatController.recorder.recording
                                             || app.chatController.pendingAudioPath.length === 0)
                                topPadding: 8
                                bottomPadding: 8
                                leftPadding: 16
                                rightPadding: 16
                                background: Rectangle {
                                    anchors.fill: parent
                                    radius: 8
                                    property color base: app.chatController.recorder.recording ? app.themeController.recordHot : app.themeController.accent
                                    color: !recordBtn.enabled ? app.themeController.borderColor : (recordBtn.pressed ? Qt.darker(base, 1.15) : (recordBtn.hovered ? Qt.lighter(base, 1.06) : base))
                                }
                                contentItem: Label {
                                    text: recordBtn.text
                                    font.bold: true
                                    color: app.themeController.onAccentText
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    if (app.chatController.recorder.recording)
                                        app.chatController.processRecorderOutput()
                                    else
                                        app.chatController.startPipelineFromRecorder()
                                }
                            }
                        }
                    }
                }
            }
            }
        }
    }

    Popup {
        id: settingsPopup
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        width: Math.min(520, parent.width - 40)
        height: Math.min(640, parent.height - 40)
        modal: true
        focus: true
        onOpened: {
            hfTokenField.text = ""
        }

        background: Rectangle {
            color: app.themeController.surface
            radius: 8
            border.color: app.themeController.borderColor
            border.width: 1
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12
            ScrollView {
                id: settingsBodyScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                ColumnLayout {
                    width: settingsBodyScroll.width
                    spacing: 12
                    ColumnLayout {
                        visible: !app.modelStatusController.mockBackend
                        Layout.fillWidth: true
                        spacing: 8
                Label {
                    text: qsTr("Speech model (WhisperX)")
                    color: app.themeController.textMuted
                    font.pixelSize: 12
                }
                Label {
                    text: app.modelStatusController.modelSummary
                    color: app.themeController.textPrimary
                    font.pixelSize: 13
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Label {
                    text: app.modelStatusController.modelReady
                        ? qsTr("✓ Model ready (offline STT)")
                        : qsTr("⚠ Speech model not ready")
                    color: app.modelStatusController.modelReady ? app.themeController.textMuted : "#f59e0b"
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Label {
                    visible: !app.modelStatusController.modelReady && app.modelStatusController.cacheStatusHint.length > 0
                    text: app.modelStatusController.cacheStatusHint
                    color: app.themeController.textMuted
                    font.pixelSize: 11
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Label {
                    text: qsTr("Weights are stored next to the project (you can move the whole folder). Cache:\n") + win.ltrIsolate(app.modelStatusController.cachePath)
                    color: app.themeController.textMuted
                    font.pixelSize: 11
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    ChromeButton {
                        text: app.modelStatusController.downloading ? qsTr("Downloading…") : qsTr("Download / resume")
                        enabled: !app.modelStatusController.modelReady && !app.modelStatusController.downloading
                        onClicked: app.modelStatusController.startDownload()
                    }
                    ChromeButton {
                        text: qsTr("Refresh status")
                        enabled: !app.modelStatusController.downloading
                        onClicked: app.modelStatusController.refresh()
                    }
                    ChromeButton {
                        flatLink: true
                        dangerLink: true
                        text: qsTr("Delete model from disk…")
                        enabled: !app.modelStatusController.downloading
                        onClicked: clearCacheConfirmDialog.open()
                    }
                }
                ProgressBar {
                    Layout.fillWidth: true
                    visible: app.modelStatusController.downloading || app.modelStatusController.downloadError.length > 0
                    from: 0
                    to: 1
                    value: app.modelStatusController.progressFraction
                    indeterminate: app.modelStatusController.downloading && !app.modelStatusController.progressTotalKnown
                }
                Label {
                    visible: app.modelStatusController.downloading && app.modelStatusController.downloadPhaseText.length > 0
                    text: app.modelStatusController.downloadPhaseText
                    color: app.themeController.textMuted
                    font.pixelSize: 10
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                RowLayout {
                    visible: app.modelStatusController.downloading
                    Layout.fillWidth: true
                    spacing: 12
                    Label {
                        text: app.modelStatusController.progressPercentText
                        color: app.themeController.textPrimary
                        font.bold: true
                        font.pixelSize: 12
                    }
                    Label {
                        text: app.modelStatusController.progressDetail
                        color: app.themeController.textMuted
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                    }
                    Label {
                        text: app.modelStatusController.throughputText
                        color: app.themeController.textMuted
                        font.pixelSize: 11
                    }
                    Label {
                        text: qsTr("ETA %1").arg(app.modelStatusController.etaText)
                        color: app.themeController.textMuted
                        font.pixelSize: 11
                    }
                }
                Label {
                    visible: app.modelStatusController.downloadError.length > 0
                    text: app.modelStatusController.downloadError
                    color: app.themeController.errorText
                    font.pixelSize: 11
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: app.themeController.borderColor
                }
            }
            Label {
                text: qsTr("Meeting files folder")
                color: app.themeController.textMuted
                font.pixelSize: 12
            }
            Label {
                text: qsTr("Each session gets a folder under \"sessions\" when you record or run the pipeline (audio, transcript .txt, summary .txt). Empty folders can be removed with the button below. Older flat subfolders may still exist from previous versions.")
                color: app.themeController.textMuted
                font.pixelSize: 11
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Label {
                text: app.settingsController.meetingFilesFolder
                color: app.themeController.textPrimary
                font.pixelSize: 11
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                ChromeButton {
                    text: qsTr("Browse…")
                    onClicked: meetingOutputFolderDialog.open()
                }
                ChromeButton {
                    text: qsTr("Use project default")
                    enabled: app.settingsController.meetingOutputRootCustom.length > 0
                    onClicked: app.settingsController.resetMeetingOutputRoot()
                }
                ChromeButton {
                    flatLink: true
                    text: qsTr("📋 Copy path")
                    onClicked: app.settingsController.copyMeetingFilesFolderPath()
                }
            }
            ChromeButton {
                text: qsTr("Remove empty session folders")
                onClicked: {
                    var n = app.settingsController.pruneEmptySessionFolders()
                    if (n > 0)
                        app.chatController.showTransientStatus(qsTr("Removed %1 empty folder(s) under sessions.").arg(n))
                    else
                        app.chatController.showTransientStatus(qsTr("No empty session folders to remove."))
                }
            }
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: app.themeController.borderColor
            }
            Label {
                text: qsTr("Hugging Face token (pyannote / speaker diarization)")
                color: app.themeController.textMuted
                font.pixelSize: 12
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Label {
                text: qsTr("Create a token at huggingface.co (read access). Accept the pyannote model conditions on the Hub first. The token is stored only on this device.")
                color: app.themeController.textMuted
                font.pixelSize: 11
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Basic.TextField {
                    id: hfTokenField
                    Layout.fillWidth: true
                    echoMode: TextInput.Password
                    placeholderText: qsTr("Paste hf_… token (leave empty to keep current)")
                    color: app.themeController.textPrimary
                    background: Rectangle {
                        color: app.themeController.inputSurface
                        radius: 6
                        border.color: app.themeController.borderColor
                        border.width: 1
                    }
                    onEditingFinished: {
                        if (text.length > 0)
                            app.settingsController.setHfAccessToken(text)
                    }
                }
                Label {
                    visible: app.settingsController.hfAccessTokenConfigured
                    text: "✓"
                    color: "#16a34a"
                    font.pixelSize: 16
                    font.bold: true
                }
                Label {
                    visible: hfTokenField.text.length > 0 && app.settingsController.hfTokenPreviewLooksValid(hfTokenField.text)
                    text: "✓"
                    color: "#16a34a"
                    font.pixelSize: 14
                }
            }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                ChromeButton {
                    flatLink: true
                    text: qsTr("📋 Copy data folder path")
                    onClicked: app.chatController.copyAppDataPath()
                }
                ChromeButton {
                    flatLink: true
                    text: qsTr("📋 Copy meeting files folder")
                    onClicked: app.chatController.copyMeetingOutputRoot()
                }
                Item { Layout.fillWidth: true }
                ChromeButton {
                    text: qsTr("✖️ Close")
                    onClicked: settingsPopup.close()
                }
            }
        }
    }

    Dialog {
        id: renameSessionDialog
        property string pendingSessionId: ""
        property string draftTitle: ""
        title: qsTr("Rename session")
        modal: true
        anchors.centerIn: parent
        width: Math.min(440, win.width - 40)
        standardButtons: Dialog.Ok | Dialog.Cancel
        ColumnLayout {
            spacing: 10
            width: Math.min(392, win.width - 48)
            Label {
                text: qsTr("Session title")
                color: app.themeController.textMuted
                font.pixelSize: 12
            }
            Basic.TextField {
                id: renameSessionField
                Layout.fillWidth: true
                color: app.themeController.textPrimary
                selectByMouse: true
                background: Rectangle {
                    color: app.themeController.inputSurface
                    radius: 6
                    border.color: app.themeController.borderColor
                    border.width: 1
                }
            }
        }
        onOpened: {
            renameSessionField.text = renameSessionDialog.draftTitle
            renameSessionField.selectAll()
            renameSessionField.forceActiveFocus()
        }
        onAccepted: {
            app.sessionController.renameSession(renameSessionDialog.pendingSessionId, renameSessionField.text)
            close()
        }
    }

    Dialog {
        id: deleteSessionDialog
        property string pendingSessionId: ""
        property string pendingTitle: ""
        title: qsTr("Delete session and files from disk?")
        modal: true
        anchors.centerIn: parent
        width: Math.min(520, win.width - 40)
        standardButtons: Dialog.NoButton
        ColumnLayout {
            spacing: 14
            width: Math.min(472, win.width - 48)
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: deleteSessionDangerBanner.implicitHeight + 20
                radius: 8
                color: app.themeController.errorBannerBackground
                border.width: 2
                border.color: app.themeController.errorBannerBorder
                ColumnLayout {
                    id: deleteSessionDangerBanner
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 6
                    Label {
                        text: qsTr("Permanent data loss")
                        font.pixelSize: 15
                        font.bold: true
                        color: app.themeController.errorText
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                    }
                    Label {
                        text: qsTr("This removes real files and chat history. The app does not move them to the Recycle Bin — they are deleted from the session folder on disk.")
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                        font.pixelSize: 12
                        color: app.themeController.textPrimary
                    }
                }
            }
            Label {
                text: qsTr("Session: \"%1\"\n\n• All messages in this session\n• The whole meeting folder under \"sessions\" (audio, transcripts, summaries, and anything else inside that folder)\n\nOnly click the red button if you accept complete loss of this data.").arg(deleteSessionDialog.pendingTitle)
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                color: app.themeController.textPrimary
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item {
                    Layout.fillWidth: true
                }
                ChromeButton {
                    id: deleteSessionCancelBtn
                    text: qsTr("Cancel")
                    onClicked: deleteSessionDialog.close()
                }
                Button {
                    id: deleteSessionConfirmBtn
                    text: qsTr("Delete session and all disk files")
                    Layout.minimumWidth: 200
                    topPadding: 8
                    bottomPadding: 8
                    leftPadding: 14
                    rightPadding: 14
                    contentItem: Label {
                        text: deleteSessionConfirmBtn.text
                        font {
                            family: deleteSessionConfirmBtn.font.family
                            pixelSize: deleteSessionConfirmBtn.font.pixelSize
                            bold: true
                        }
                        color: app.themeController.onAccentText
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                        width: deleteSessionConfirmBtn.availableWidth
                    }
                    background: Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: deleteSessionConfirmBtn.pressed
                               ? "#7f1d1d"
                               : (deleteSessionConfirmBtn.hovered ? "#b91c1c" : "#991b1b")
                        border.width: 2
                        border.color: deleteSessionConfirmBtn.pressed ? "#450a0a" : "#fca5a5"
                    }
                    onClicked: {
                        app.sessionController.deleteSession(deleteSessionDialog.pendingSessionId)
                        deleteSessionDialog.close()
                    }
                }
            }
        }
        onOpened: deleteSessionCancelBtn.forceActiveFocus()
    }

    Dialog {
        id: stopProcessingDialog
        title: qsTr("Stop processing?")
        modal: true
        anchors.centerIn: parent
        width: Math.min(480, win.width - 40)
        standardButtons: Dialog.NoButton
        ColumnLayout {
            spacing: 16
            width: Math.min(432, win.width - 48)
            Label {
                text: qsTr("This will request to stop transcription or summarization. The current step may take a moment to finish (especially while the local speech or language model is working). Do you want to stop?")
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                color: app.themeController.textPrimary
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item {
                    Layout.fillWidth: true
                }
                ChromeButton {
                    id: stopProcessingCancelBtn
                    text: qsTr("Cancel")
                    onClicked: stopProcessingDialog.close()
                }
                Button {
                    id: stopProcessingConfirmBtn
                    text: qsTr("Stop")
                    topPadding: 8
                    bottomPadding: 8
                    leftPadding: 14
                    rightPadding: 14
                    contentItem: Label {
                        text: stopProcessingConfirmBtn.text
                        font {
                            family: stopProcessingConfirmBtn.font.family
                            pixelSize: stopProcessingConfirmBtn.font.pixelSize
                            bold: true
                        }
                        color: app.themeController.onAccentText
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: stopProcessingConfirmBtn.pressed
                               ? "#b91c1c"
                               : (stopProcessingConfirmBtn.hovered ? "#f87171" : "#dc2626")
                        border.width: 0
                    }
                    onClicked: {
                        app.chatController.requestStopProcessing()
                        stopProcessingDialog.close()
                    }
                }
            }
        }
        onOpened: stopProcessingCancelBtn.forceActiveFocus()
    }

    Dialog {
        id: clearCacheConfirmDialog
        title: qsTr("Delete Whisper model from disk?")
        modal: true
        anchors.centerIn: parent
        width: Math.min(520, win.width - 40)
        standardButtons: Dialog.NoButton
        ColumnLayout {
            spacing: 14
            width: Math.min(472, win.width - 48)
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: clearCacheDangerBanner.implicitHeight + 20
                radius: 8
                color: app.themeController.errorBannerBackground
                border.width: 2
                border.color: app.themeController.errorBannerBorder
                ColumnLayout {
                    id: clearCacheDangerBanner
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 6
                    Label {
                        text: qsTr("Permanent data loss")
                        font.pixelSize: 15
                        font.bold: true
                        color: app.themeController.errorText
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                    }
                    Label {
                        text: qsTr("You are about to delete large model files from your disk. This is not undoable here — you must download the weights again for offline speech.")
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                        font.pixelSize: 12
                        color: app.themeController.textPrimary
                    }
                }
            }
            Label {
                text: qsTr("The entire Whisper / WhisperX cache folder will be erased (often several gigabytes). Offline transcription will not work until you use \"Download / resume\" again.\n\nOnly use the red button if you intend to free disk space and accept re-downloading.")
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                color: app.themeController.textPrimary
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item {
                    Layout.fillWidth: true
                }
                ChromeButton {
                    id: clearCacheCancelBtn
                    text: qsTr("Cancel")
                    onClicked: clearCacheConfirmDialog.close()
                }
                Button {
                    id: clearCacheRemoveBtn
                    text: qsTr("Delete model files from disk")
                    Layout.minimumWidth: 200
                    topPadding: 8
                    bottomPadding: 8
                    leftPadding: 14
                    rightPadding: 14
                    contentItem: Label {
                        text: clearCacheRemoveBtn.text
                        font {
                            family: clearCacheRemoveBtn.font.family
                            pixelSize: clearCacheRemoveBtn.font.pixelSize
                            bold: true
                        }
                        color: app.themeController.onAccentText
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                        width: clearCacheRemoveBtn.availableWidth
                    }
                    background: Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: clearCacheRemoveBtn.pressed
                               ? "#7f1d1d"
                               : (clearCacheRemoveBtn.hovered ? "#b91c1c" : "#991b1b")
                        border.width: 2
                        border.color: clearCacheRemoveBtn.pressed ? "#450a0a" : "#fca5a5"
                    }
                    onClicked: {
                        app.modelStatusController.clearWhisperModelCache()
                        clearCacheConfirmDialog.close()
                    }
                }
            }
        }
        onOpened: clearCacheCancelBtn.forceActiveFocus()
    }

    Dialog {
        id: debugDialog
        property string debugMessage: ""
        title: qsTr("Debug")
        standardButtons: Dialog.Ok
        modal: true
        anchors.centerIn: parent
        width: Math.min(480, parent.width - 32)
        MarkdownBody {
            text: debugDialog.debugMessage
            width: debugDialog.availableWidth
            color: app.themeController.textPrimary
        }
        onAccepted: close()
    }

    Connections {
        target: app.debugNotifier
        function onNotify(msg) {
            debugDialog.debugMessage = msg
            debugDialog.open()
        }
    }

    FolderDialog {
        id: meetingOutputFolderDialog
        title: qsTr("Choose meeting files folder")
        onAccepted: {
            if (meetingOutputFolderDialog.selectedFolder)
                app.settingsController.setMeetingOutputRootFromUrl(meetingOutputFolderDialog.selectedFolder)
        }
    }
}
