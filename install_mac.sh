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
    [ -d "$BACKUP_DIR/memory" ]     && cp -r "$BACKUP_DIR/memory"   "$INSTALL_DIR/memory"             && echo "   ✅ memory/ wiederhergestellt"
    [ -d "$BACKUP_DIR/RAG" ]        && cp -r "$BACKUP_DIR/RAG"      "$INSTALL_DIR/RAG"                && echo "   ✅ RAG/ wiederhergestellt"
    [ -d "$BACKUP_DIR/gen_images" ] && cp -r "$BACKUP_DIR/gen_images" "$INSTALL_DIR/gen_images"       && echo "   ✅ gen_images/ wiederhergestellt"

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
./venv/bin/python3 -m pip install --no-compile faster-whisper sounddevice numpy requests PySide6 sentence-transformers pyobjc-framework-Speech -q

# 7. Desktop-Verknüpfung erstellen
DESKTOP_DIR="$HOME/Desktop"
START_SCRIPT="$DESKTOP_DIR/Starte_Trinity.command"

echo "📝 Erstelle Start-Verknüpfung auf dem Desktop..."
cat << 'EOF' > "$START_SCRIPT"
#!/bin/bash
cd "$HOME/Trinity_Assistant" || exit
echo "Starte Trinity..."
./venv/bin/python3 trinity_launcher.py
EOF

chmod +x "$START_SCRIPT"

echo "🖼️ Setze Trinity-Icon für den Desktop-Button..."
./venv/bin/python3 -c "
import Cocoa, sys
image = Cocoa.NSImage.alloc().initWithContentsOfFile_('$INSTALL_DIR/core/icon.png')
if image:
    Cocoa.NSWorkspace.sharedWorkspace().setIcon_forFile_options_(image, '$START_SCRIPT', 0)
" 2>/dev/null || true

echo ""
echo "🎉 ${IS_UPDATE:+Update}${IS_UPDATE:-Installation} erfolgreich abgeschlossen!"
echo "============================================"
echo "👉 Ein Start-Icon ('Starte_Trinity.command') liegt auf deinem Schreibtisch."
echo "👉 Doppelklicke einfach darauf, um Trinity zu starten."
if [ "$IS_UPDATE" = true ]; then
echo ""
echo "✅ Alle deine Konfigurationen (API-Keys, Soul.md, User.md, RAG, Transkripte)"
echo "   wurden automatisch aus der alten Version übernommen."
fi
echo ""
