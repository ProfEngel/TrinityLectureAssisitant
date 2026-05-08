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
echo "📂 Installiere Trinity in: $INSTALL_DIR"

if [ -d "$INSTALL_DIR" ]; then
    echo "⚠️ Verzeichnis existiert bereits. Erstelle Backup..."
    mv "$INSTALL_DIR" "${INSTALL_DIR}_backup_$(date +%s)"
fi

# 3. Projekt herunterladen (Git Clone, falls Git existiert, ansonsten ZIP)
if command -v git &> /dev/null; then
    echo "📥 Lade Repository herunter (via Git)..."
    git clone https://github.com/ProfEngel/TrinityLectureAssisitant.git "$INSTALL_DIR"
else
    echo "📥 Lade Repository herunter (via ZIP)..."
    curl -L -o trinity.zip https://github.com/ProfEngel/TrinityLectureAssisitant/archive/refs/heads/main.zip
    unzip -q trinity.zip
    mv TrinityLectureAssisitant-main "$INSTALL_DIR"
    rm trinity.zip
fi

# 4. Virtuelles Environment erstellen
echo "🐍 Erstelle virtuelle Python-Umgebung..."
cd "$INSTALL_DIR" || exit
python3 -m venv venv

# 5. Abhängigkeiten installieren
echo "📦 Installiere Abhängigkeiten (das kann einen Moment dauern)..."
./venv/bin/python3 -m pip install --upgrade pip
./venv/bin/python3 -m pip install faster-whisper sounddevice numpy requests PySide6 sentence-transformers pyobjc-framework-Speech

# 6. Start-Skript für den Desktop erstellen
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

echo ""
echo "🎉 Installation erfolgreich abgeschlossen!"
echo "========================================"
echo "👉 Ein Start-Icon ('Starte_Trinity.command') wurde auf deinem Schreibtisch abgelegt."
echo "👉 Doppelklicke einfach darauf, um Trinity in Zukunft zu starten."
echo ""
echo "Hinweis: Bitte vergiss nicht, deine API-Keys (OpenRouter/Fal.ai) in der core/config.json einzutragen,"
echo "oder nutze das Setup-UI: python3 core/settings_ui.py"
echo ""
