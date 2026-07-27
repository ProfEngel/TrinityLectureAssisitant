#!/bin/bash
set -euo pipefail

# Pfade definieren
PROJECT_DIR="$(pwd)"
APP_NAME="Trinity"
APPLICATIONS_DIR="$HOME/Applications"
DESKTOP_DIR="$HOME/Desktop"
APP_PATH="$APPLICATIONS_DIR/$APP_NAME.app"
DESKTOP_LINK="$DESKTOP_DIR/$APP_NAME.app"
BACKUP_DIR="${TRINITY_APP_BACKUP_DIR:-$HOME/Trinity-Recovery/app-backups/$(date +%Y%m%d_%H%M%S)}"
ICON_PNG="$PROJECT_DIR/core/icon.png"
ICON_ICNS="$PROJECT_DIR/assets/trinity_icon.icns"
ICONSET_DIR="/tmp/TrinityIcon.iconset"
ICNS_TMP="/tmp/trinity_icon.icns"
ICNS_TARGET="$APP_PATH/Contents/Resources/Trinity.icns"

echo "🚀 Erstelle native macOS App für Trinity..."

# Die eigentliche App liegt bewusst nicht auf dem möglicherweise durch iCloud
# verwalteten Desktop. Dateianbieter-Metadaten können eine lokale Signatur
# nachträglich ungültig machen. Auf dem Desktop liegt nur ein Verweis.
mkdir -p "$APPLICATIONS_DIR" "$DESKTOP_DIR" "$BACKUP_DIR"
if [ -e "$APP_PATH" ]; then
    mv "$APP_PATH" "$BACKUP_DIR/Trinity.app.previous"
fi

# 2. AppleScript Applet erstellen
# Wir nutzen 'do shell script' um Trinity zu starten. 
# Wir führen es im Hintergrund aus (&), damit das Applet selbst sofort fertig ist, 
# oder wir lassen es offen. 
cat << 'EOF' > /tmp/trinity_app.applescript
set configFile to "PROJECT_DIR/core/config.json"
set showTerminal to false
try
    set configText to do shell script "cat '" & configFile & "'"
    if configText contains "\"show_terminal\": true" then
        set showTerminal to true
    end if
end try

set trinityRunning to false
try
    do shell script "/usr/bin/curl --silent --fail --max-time 1 http://127.0.0.1:8765/health >/dev/null"
    set trinityRunning to true
end try

if trinityRunning then
    open location "http://127.0.0.1:8765/#werkstatt"
else if showTerminal then
    tell application "Terminal"
        do script "cd 'PROJECT_DIR' && ./venv/bin/python3 trinity_launcher.py"
        activate
    end tell
else
    do shell script "mkdir -p 'PROJECT_DIR/logs' && cd 'PROJECT_DIR' && ./venv/bin/python3 trinity_launcher.py >> 'PROJECT_DIR/logs/desktop-launch.log' 2>&1 &"
end if
EOF
sed -i '' "s|PROJECT_DIR|$PROJECT_DIR|g" /tmp/trinity_app.applescript
osacompile -o "$APP_PATH" /tmp/trinity_app.applescript
rm /tmp/trinity_app.applescript

echo "🖼️  Setze Icon für $APP_NAME.app..."

# 3. Bundle-Icon setzen. Ein echtes .icns im App-Bundle ist zuverlässiger als
# ein Finder-Custom-Icon und erscheint bereits vor dem ersten Start der App.
if [ -f "$ICON_ICNS" ]; then
    cp "$ICON_ICNS" "$ICNS_TARGET"
    /usr/libexec/PlistBuddy -c "Set :CFBundleIconFile Trinity" "$APP_PATH/Contents/Info.plist" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Set :CFBundleIconName Trinity" "$APP_PATH/Contents/Info.plist" 2>/dev/null || true
    touch "$APP_PATH/Contents/Info.plist" "$APP_PATH"
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_PATH" 2>/dev/null || true
elif [ -f "$ICON_PNG" ]; then
    rm -rf "$ICONSET_DIR" "$ICNS_TMP"
    mkdir -p "$ICONSET_DIR"
    sips -z 16   16   "$ICON_PNG" --out "$ICONSET_DIR/icon_16x16.png"       &>/dev/null
    sips -z 32   32   "$ICON_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png"    &>/dev/null
    sips -z 32   32   "$ICON_PNG" --out "$ICONSET_DIR/icon_32x32.png"       &>/dev/null
    sips -z 64   64   "$ICON_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png"    &>/dev/null
    sips -z 128  128  "$ICON_PNG" --out "$ICONSET_DIR/icon_128x128.png"     &>/dev/null
    sips -z 256  256  "$ICON_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png"  &>/dev/null
    sips -z 256  256  "$ICON_PNG" --out "$ICONSET_DIR/icon_256x256.png"     &>/dev/null
    sips -z 512  512  "$ICON_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png"  &>/dev/null
    sips -z 512  512  "$ICON_PNG" --out "$ICONSET_DIR/icon_512x512.png"     &>/dev/null
    sips -z 1024 1024 "$ICON_PNG" --out "$ICONSET_DIR/icon_512x512@2x.png"  &>/dev/null
    iconutil -c icns "$ICONSET_DIR" -o "$ICNS_TMP"
    cp "$ICNS_TMP" "$ICNS_TARGET"
    /usr/libexec/PlistBuddy -c "Set :CFBundleIconFile Trinity" "$APP_PATH/Contents/Info.plist" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Set :CFBundleIconName Trinity" "$APP_PATH/Contents/Info.plist" 2>/dev/null || true
    touch "$APP_PATH/Contents/Info.plist" "$APP_PATH"
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_PATH" 2>/dev/null || true
    rm -rf "$ICONSET_DIR" "$ICNS_TMP"
else
    echo "⚠️  $ICON_PNG nicht gefunden – App-Icon bleibt Standard."
fi

# Erst das vollständige Bundle bereinigen und danach lokal signieren.
xattr -cr "$APP_PATH" 2>/dev/null || true
/usr/bin/codesign --force --deep --sign - "$APP_PATH"
/usr/bin/codesign --verify --deep --strict --verbose=2 "$APP_PATH"

if [ -L "$DESKTOP_LINK" ]; then
    rm "$DESKTOP_LINK"
elif [ -e "$DESKTOP_LINK" ]; then
    mv "$DESKTOP_LINK" "$BACKUP_DIR/Trinity-Desktop.app.previous"
fi
ln -s "$APP_PATH" "$DESKTOP_LINK"

echo "✅ Fertig! Die signierte App liegt unter $APP_PATH."
echo "👉 Auf dem Schreibtisch liegt ein Verweis auf diese App."
echo "👉 Du kannst es jetzt einfach in deine Dock-Leiste ziehen."
