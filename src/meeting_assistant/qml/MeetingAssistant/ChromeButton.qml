import QtQuick
import QtQuick.Controls

// Neutral chrome button — uses app.themeController (root context).
Button {
    id: root

    /// Flat text-only action (e.g. Copy path); accent-colored label, hover wash.
    property bool flatLink: false

    /// When used with `flatLink`, use destructive red styling instead of accent blue.
    property bool dangerLink: false

    topPadding: flatLink ? 6 : 8
    bottomPadding: flatLink ? 6 : 8
    leftPadding: flatLink ? 8 : 14
    rightPadding: flatLink ? 8 : 14

    opacity: enabled ? 1.0 : 0.48

    background: Rectangle {
        anchors.fill: parent
        radius: 6
        visible: !flatLink || root.hovered || root.pressed
        color: flatLink
               ? (root.pressed ? app.themeController.chromePressed
                               : (root.hovered
                                  ? (dangerLink ? app.themeController.errorBannerBackground
                                                : app.themeController.linkHoverBackground)
                                  : "transparent"))
               : (root.pressed ? app.themeController.chromePressed
                               : (root.hovered ? app.themeController.chromeHover : app.themeController.surface))
        border.width: flatLink ? 0 : 1
        border.color: app.themeController.borderColor
    }

    contentItem: Label {
        text: root.text
        font: root.font
        color: flatLink
               ? (dangerLink ? app.themeController.errorText : app.themeController.accent)
               : app.themeController.textPrimary
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
