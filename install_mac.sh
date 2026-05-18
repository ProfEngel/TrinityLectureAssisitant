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
./venv/bin/python3 -m pip install --no-compile faster-whisper sounddevice numpy requests PySide6 sentence-transformers pyobjc-framework-Speech pyobjc-framework-AVFoundation beautifulsoup4 -q

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

echo "🖼️ Setze Trinity-Icon für die App..."
./venv/bin/python3 -c "
import Cocoa, sys
image = Cocoa.NSImage.alloc().initWithContentsOfFile_('$INSTALL_DIR/core/icon.png')
if image:
    Cocoa.NSWorkspace.sharedWorkspace().setIcon_forFile_options_(image, '$APP_PATH', 0)
" 2>/dev/null || true

echo ""
echo "🎉 ${IS_UPDATE:+Update}${IS_UPDATE:-Installation} erfolgreich abgeschlossen!"
echo "============================================"
echo "👉 Eine native App ('Trinity.app') liegt auf deinem Schreibtisch."
echo "👉 Doppelklicke einfach darauf, um Trinity zu starten."
echo "👉 Du kannst sie auch in deine Dock-Leiste ziehen."
if [ "$IS_UPDATE" = true ]; then
echo ""
echo "✅ Alle deine Konfigurationen (API-Keys, Soul.md, User.md, RAG, Transkripte)"
echo "   wurden automatisch aus der alten Version übernommen."
fi
echo ""
