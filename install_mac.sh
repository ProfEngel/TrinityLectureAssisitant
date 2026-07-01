#!/bin/bash

echo "🧞‍♀️ Willkommen beim Trinity Assistant Installer für macOS"
echo "======================================================"
echo ""

# 1. Python prüfen
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 ist nicht installiert. Bitte installiere Python 3 (z.B. via Homebrew: brew install python3) und versuche es erneut."
    exit 1
fi
echo "✅ Python3 ist installiert."

# 2. Zielverzeichnis festlegen
INSTALL_DIR="$HOME/Trinity_Assistant"
BACKUP_DIR="${INSTALL_DIR}_config_backup_$(date +%Y%m%d_%H%M%S)"

# 3. Update-Modus: Bestehende Configs sichern
IS_UPDATE=false
if [ -d "$INSTALL_DIR" ]; then
    IS_UPDATE=true
    echo ""
    echo "🔄 Bestehende Installation erkannt – starte Update-Modus."
    echo "   Deine Konfigurationen werden gesichert und danach wiederhergestellt."
    echo ""

    mkdir -p "$BACKUP_DIR"

    # Nutzerdaten sichern
    [ -f "$INSTALL_DIR/core/config.json" ]  && cp "$INSTALL_DIR/core/config.json"  "$BACKUP_DIR/config.json"  && echo "   💾 config.json gesichert"
    [ -f "$INSTALL_DIR/core/Soul.md" ]      && cp "$INSTALL_DIR/core/Soul.md"      "$BACKUP_DIR/Soul.md"      && echo "   💾 Soul.md gesichert"
    [ -f "$INSTALL_DIR/core/User.md" ]      && cp "$INSTALL_DIR/core/User.md"      "$BACKUP_DIR/User.md"      && echo "   💾 User.md gesichert"
    [ -d "$INSTALL_DIR/memory" ]            && cp -r "$INSTALL_DIR/memory"         "$BACKUP_DIR/memory"       && echo "   💾 memory/ (Transkripte) gesichert"
    [ -d "$INSTALL_DIR/RAG" ]               && cp -r "$INSTALL_DIR/RAG"            "$BACKUP_DIR/RAG"          && echo "   💾 RAG/ (Wissensbasis) gesichert"
    [ -d "$INSTALL_DIR/gen_images" ]        && cp -r "$INSTALL_DIR/gen_images"     "$BACKUP_DIR/gen_images"   && echo "   💾 gen_images/ gesichert"
    [ -d "$INSTALL_DIR/TrinityRuntime" ]    && cp -r "$INSTALL_DIR/TrinityRuntime" "$BACKUP_DIR/TrinityRuntime" && echo "   💾 TrinityRuntime/ gesichert"

    echo ""
    echo "   📁 Backup gespeichert unter: $BACKUP_DIR"

    # Alten Ordner entfernen (aber Backup ist bereits sicher)
    rm -rf "$INSTALL_DIR"
fi

# 4. Neue Version herunterladen
echo ""
echo "📥 Lade aktuelle Trinity-Version herunter..."
if command -v git &> /dev/null; then
    git clone https://github.com/ProfEngel/TrinityLectureAssisitant.git "$INSTALL_DIR"
else
    curl -L -o trinity.zip https://github.com/ProfEngel/TrinityLectureAssisitant/archive/refs/heads/main.zip
    unzip -q trinity.zip
    mv TrinityLectureAssisitant-main "$INSTALL_DIR"
    rm trinity.zip
fi

# 5. Gesicherte Configs wiederherstellen (Update-Modus)
if [ "$IS_UPDATE" = true ]; then
    echo ""
    echo "♻️  Stelle deine Konfigurationen wieder her..."

    [ -f "$BACKUP_DIR/config.json" ] && cp "$BACKUP_DIR/config.json" "$INSTALL_DIR/core/config.json"  && echo "   ✅ config.json wiederhergestellt"
    [ -f "$BACKUP_DIR/Soul.md" ]    && cp "$BACKUP_DIR/Soul.md"     "$INSTALL_DIR/core/Soul.md"       && echo "   ✅ Soul.md wiederhergestellt"
    [ -f "$BACKUP_DIR/User.md" ]    && cp "$BACKUP_DIR/User.md"     "$INSTALL_DIR/core/User.md"       && echo "   ✅ User.md wiederhergestellt"
    [ -d "$BACKUP_DIR/memory" ]     && mkdir -p "$INSTALL_DIR/memory" && cp -a "$BACKUP_DIR/memory/." "$INSTALL_DIR/memory/" && echo "   ✅ memory/ wiederhergestellt"
    [ -d "$BACKUP_DIR/RAG" ]        && mkdir -p "$INSTALL_DIR/RAG" && cp -a "$BACKUP_DIR/RAG/." "$INSTALL_DIR/RAG/" && echo "   ✅ RAG/ wiederhergestellt"
    [ -d "$BACKUP_DIR/gen_images" ] && mkdir -p "$INSTALL_DIR/gen_images" && cp -a "$BACKUP_DIR/gen_images/." "$INSTALL_DIR/gen_images/" && echo "   ✅ gen_images/ wiederhergestellt"
    [ -d "$BACKUP_DIR/TrinityRuntime" ] && mkdir -p "$INSTALL_DIR/TrinityRuntime" && cp -a "$BACKUP_DIR/TrinityRuntime/." "$INSTALL_DIR/TrinityRuntime/" && echo "   ✅ TrinityRuntime/ wiederhergestellt"

    echo ""
    echo "   🗑️  Temporäres Backup wird entfernt..."
    rm -rf "$BACKUP_DIR"
fi

# 6. Virtuelle Umgebung erstellen & Pakete installieren
echo ""
echo "🐍 Erstelle virtuelle Python-Umgebung (Sandbox)..."
cd "$INSTALL_DIR" || exit
python3 -m venv venv

echo "📦 Installiere Abhängigkeiten (das kann 2–5 Minuten dauern)..."
export PYTHONIOENCODING=utf-8
./venv/bin/python3 -m pip install --upgrade pip -q
./venv/bin/python3 -m pip install --no-compile ".[macos]" -q

# 6.5 Benutzerweiten CLI-Befehl installieren
CLI_BIN="$HOME/.local/bin"
CLI_PATH="$CLI_BIN/trinity"
mkdir -p "$CLI_BIN"
cat > "$CLI_PATH" << EOF
#!/bin/sh
exec "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/trinity_cli.py" "\$@"
EOF
chmod +x "$CLI_PATH"

ZPROFILE="$HOME/.zprofile"
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
if [ ! -f "$ZPROFILE" ] || ! grep -Fq "$PATH_LINE" "$ZPROFILE"; then
    echo "" >> "$ZPROFILE"
    echo "# Trinity Assistant CLI" >> "$ZPROFILE"
    echo "$PATH_LINE" >> "$ZPROFILE"
fi
export PATH="$CLI_BIN:$PATH"

# 6.6 MainHub / Control Plane idempotent vorbereiten
echo "🧭 Prüfe MainHub-/Control-Plane-Ordner..."
./venv/bin/python3 trinity_cli.py --home "$INSTALL_DIR" control-plane init >/dev/null 2>&1 || \
    echo "   ⚠️  Control Plane konnte jetzt nicht initialisiert werden. Später möglich mit: trinity control-plane init"

# 7. Desktop-Verknüpfung (Native macOS App) erstellen
DESKTOP_DIR="$HOME/Desktop"
APP_PATH="$DESKTOP_DIR/Trinity.app"

echo "📝 Erstelle native macOS App auf dem Desktop..."
# Alte .command Verknüpfung entfernen, falls vorhanden
rm -f "$DESKTOP_DIR/Starte_Trinity.command"
rm -rf "$APP_PATH"

cat << 'EOF' > /tmp/trinity_app.applescript
set configFile to "INSTALL_DIR/core/config.json"
set showTerminal to false
try
    set configText to do shell script "cat '" & configFile & "'"
    if configText contains "\"show_terminal\": true" then
        set showTerminal to true
    end if
end try

if showTerminal then
    tell application "Terminal"
        do script "cd 'INSTALL_DIR' && ./venv/bin/python3 trinity_launcher.py"
        activate
    end tell
else
    do shell script "cd 'INSTALL_DIR' && ./venv/bin/python3 trinity_launcher.py > /dev/null 2>&1 &"
end if
EOF
sed -i '' "s|INSTALL_DIR|$INSTALL_DIR|g" /tmp/trinity_app.applescript
osacompile -o "$APP_PATH" /tmp/trinity_app.applescript
rm /tmp/trinity_app.applescript

echo "🖼️  Baue Trinity-Icon (.icns) und setze es im App-Bundle..."
ICON_SRC="$INSTALL_DIR/core/icon.png"
ICON_ICNS_SRC="$INSTALL_DIR/assets/trinity_icon.icns"
ICONSET_DIR="/tmp/TrinityIcon.iconset"
ICNS_TARGET="$APP_PATH/Contents/Resources/Trinity.icns"

if [ -f "$ICON_ICNS_SRC" ]; then
    cp "$ICON_ICNS_SRC" "$ICNS_TARGET"
    /usr/libexec/PlistBuddy -c "Set :CFBundleIconFile Trinity" "$APP_PATH/Contents/Info.plist" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Set :CFBundleIconName Trinity" "$APP_PATH/Contents/Info.plist" 2>/dev/null || true
    touch "$APP_PATH/Contents/Info.plist" "$APP_PATH"
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_PATH" 2>/dev/null || true
    echo "   ✅ Trinity-Icon (.icns) gesetzt."
elif [ -f "$ICON_SRC" ]; then
    # Alle benötigten Größen erzeugen
    rm -rf "$ICONSET_DIR" && mkdir -p "$ICONSET_DIR"
    sips -z 16   16   "$ICON_SRC" --out "$ICONSET_DIR/icon_16x16.png"       &>/dev/null
    sips -z 32   32   "$ICON_SRC" --out "$ICONSET_DIR/icon_16x16@2x.png"    &>/dev/null
    sips -z 32   32   "$ICON_SRC" --out "$ICONSET_DIR/icon_32x32.png"       &>/dev/null
    sips -z 64   64   "$ICON_SRC" --out "$ICONSET_DIR/icon_32x32@2x.png"    &>/dev/null
    sips -z 128  128  "$ICON_SRC" --out "$ICONSET_DIR/icon_128x128.png"     &>/dev/null
    sips -z 256  256  "$ICON_SRC" --out "$ICONSET_DIR/icon_128x128@2x.png"  &>/dev/null
    sips -z 256  256  "$ICON_SRC" --out "$ICONSET_DIR/icon_256x256.png"     &>/dev/null
    sips -z 512  512  "$ICON_SRC" --out "$ICONSET_DIR/icon_256x256@2x.png"  &>/dev/null
    sips -z 512  512  "$ICON_SRC" --out "$ICONSET_DIR/icon_512x512.png"     &>/dev/null
    sips -z 1024 1024 "$ICON_SRC" --out "$ICONSET_DIR/icon_512x512@2x.png" &>/dev/null
    # .icns bauen und direkt ins Bundle kopieren
    iconutil -c icns "$ICONSET_DIR" -o /tmp/trinity_icon.icns
    cp /tmp/trinity_icon.icns "$ICNS_TARGET"
    /usr/libexec/PlistBuddy -c "Set :CFBundleIconFile Trinity" "$APP_PATH/Contents/Info.plist" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Set :CFBundleIconName Trinity" "$APP_PATH/Contents/Info.plist" 2>/dev/null || true
    touch "$APP_PATH/Contents/Info.plist" "$APP_PATH"
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_PATH" 2>/dev/null || true
    # Auch im Projekt-Assets ablegen für spätere Verwendung
    cp /tmp/trinity_icon.icns "$INSTALL_DIR/assets/trinity_icon.icns"
    rm -rf "$ICONSET_DIR" /tmp/trinity_icon.icns
    echo "   ✅ Trinity-Icon (.icns) gesetzt."
else
    echo "   ⚠️  icon.png nicht gefunden – App-Icon bleibt Standard."
fi

echo ""
echo "🎉 ${IS_UPDATE:+Update}${IS_UPDATE:-Installation} erfolgreich abgeschlossen!"
echo "============================================"
echo "👉 Eine native App ('Trinity.app') liegt auf deinem Schreibtisch."
echo "👉 Doppelklicke einfach darauf, um Trinity zu starten."
echo "👉 Du kannst sie auch in deine Dock-Leiste ziehen."
echo "👉 In einem neuen Terminal steht außerdem der Befehl 'trinity' bereit."
if [ "$IS_UPDATE" = true ]; then
echo ""
echo "✅ Alle deine Konfigurationen (API-Keys, Soul.md, User.md, RAG, Transkripte, TrinityRuntime)"
echo "   wurden automatisch aus der alten Version übernommen."
fi
echo ""
