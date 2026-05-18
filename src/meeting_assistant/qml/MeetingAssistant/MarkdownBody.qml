import QtQuick
import QtQuick.Controls

// Read-only body for assistant/system Markdown; set markdownEnabled false for plain user text.
Label {
    id: root

    property bool markdownEnabled: true

    wrapMode: Text.Wrap
    textFormat: markdownEnabled ? Text.MarkdownText : Text.PlainText
    linkColor: app.themeController.accent

    onLinkActivated: function (link) {
        app.chatController.openExternalLink(link)
    }
}
