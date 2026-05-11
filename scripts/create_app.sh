#!/bin/bash

# Pfade definieren
PROJECT_DIR="$(pwd)"
APP_NAME="Trinity"
DESKTOP_DIR="$HOME/Desktop"
APP_PATH="$DESKTOP_DIR/$APP_NAME.app"
ICON_PNG="$PROJECT_DIR/core/icon.png"

echo "🚀 Erstelle native macOS App für Trinity..."

# 1. Alte App entfernen falls vorhanden
rm -rf "$APP_PATH"

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

if showTerminal then
    tell application "Terminal"
        do script "cd 'PROJECT_DIR' && ./venv/bin/python3 trinity_launcher.py"
        activate
    end tell
else
    do shell script "cd 'PROJECT_DIR' && ./venv/bin/python3 trinity_launcher.py > /dev/null 2>&1 &"
end if
EOF
sed -i '' "s|PROJECT_DIR|$PROJECT_DIR|g" /tmp/trinity_app.applescript
osacompile -o "$APP_PATH" /tmp/trinity_app.applescript
rm /tmp/trinity_app.applescript

echo "🖼️  Setze Icon für $APP_NAME.app..."

# 3. Icon setzen (via Python/Cocoa wie im Installer)
./venv/bin/python3 -c "
import Cocoa, sys
image = Cocoa.NSImage.alloc().initWithContentsOfFile_('$ICON_PNG')
if image:
    Cocoa.NSWorkspace.sharedWorkspace().setIcon_forFile_options_(image, '$APP_PATH', 0)
" 2>/dev/null || true

echo "✅ Fertig! Du findest '$APP_NAME.app' auf deinem Desktop."
echo "👉 Du kannst es jetzt einfach in deine Dock-Leiste ziehen."
