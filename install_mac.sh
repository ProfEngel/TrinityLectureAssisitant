#!/bin/bash
set -euo pipefail

echo "🧞‍♀️ Willkommen beim Trinity Assistant Installer für macOS"
echo "======================================================"
echo ""

# 1. Unterstütztes Python auswählen. Apples /usr/bin/python3 ist auf vielen
# Macs noch Python 3.9 und damit außerhalb des unterstützten Bereichs.
PYTHON_BIN=""
PYTHON_CANDIDATES=()
[ -n "${TRINITY_PYTHON:-}" ] && PYTHON_CANDIDATES+=("$TRINITY_PYTHON")
if command -v brew >/dev/null 2>&1; then
    BREW_PYTHON_313="$(brew --prefix python@3.13 2>/dev/null || true)/bin/python3.13"
    [ -x "$BREW_PYTHON_313" ] && PYTHON_CANDIDATES+=("$BREW_PYTHON_313")
fi
for candidate_name in python3.13 python3.14 python3.12 python3.11 python3.10 python3; do
    candidate_path="$(command -v "$candidate_name" 2>/dev/null || true)"
    [ -n "$candidate_path" ] && PYTHON_CANDIDATES+=("$candidate_path")
done

for candidate in "${PYTHON_CANDIDATES[@]}"; do
    if "$candidate" -c 'import ssl, struct, sys, venv; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 15) and struct.calcsize("P") * 8 == 64 else 1)' >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Trinity benötigt ein 64-Bit-Python 3.10 bis 3.14 mit SSL und venv."
    echo "   Empfohlen auf dem Mac: brew install python@3.13"
    echo "   Alternativ: TRINITY_PYTHON=/pfad/zu/python3.13 install_mac.sh"
    exit 1
fi
echo "✅ Verwende $($PYTHON_BIN --version 2>&1) unter $PYTHON_BIN."

# 2. Zielverzeichnis festlegen
INSTALL_DIR="$HOME/Trinity_Assistant"
STAMP="$(date +%Y%m%d_%H%M%S)"
RECOVERY_ROOT="$HOME/Trinity-Recovery/installer-$STAMP"
BACKUP_DIR="$RECOVERY_ROOT/Nutzerdaten"
ROLLBACK_DIR="$RECOVERY_ROOT/Trinity_Assistant-vorher"
REPOSITORY="https://github.com/ProfEngel/TrinityLectureAssisitant.git"
CANVAS_DIR="$INSTALL_DIR/components/TrinityCanvas"

stop_trinity_processes() {
    local targets=""
    local pid parent command cwd

    while IFS= read -r pid; do
        [ -n "$pid" ] || continue
        command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
        case "$command" in
            *"$INSTALL_DIR/core/transcriber.py"*|*"$INSTALL_DIR/core/trinity_bridge.py"*|*"$INSTALL_DIR/trinity_console.py"*|*"$INSTALL_DIR/trinity_app.py"*|*"$INSTALL_DIR/trinity_classic.py"*|*"$INSTALL_DIR/components/TrinityCanvas/"*)
                targets="$targets $pid"
                parent="$(ps -p "$pid" -o ppid= 2>/dev/null | tr -d ' ' || true)"
                [ -n "$parent" ] && targets="$targets $parent"
                ;;
        esac
    done < <(pgrep -f "$INSTALL_DIR" 2>/dev/null || true)

    # Der Launcher selbst wird mit relativem Skriptpfad gestartet. Sein CWD
    # identifiziert die betroffene Installation eindeutig.
    while IFS= read -r pid; do
        [ -n "$pid" ] || continue
        cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1)"
        [ "$cwd" = "$INSTALL_DIR" ] && targets="$targets $pid"
    done < <(pgrep -f 'trinity_launcher.py' 2>/dev/null || true)

    targets="$(printf '%s\n' $targets | awk 'NF && !seen[$1]++ {print $1}')"
    [ -n "$targets" ] || return 0

    echo "   🛑 Beende die laufende Trinity-Instanz für das Update..."
    kill -TERM $targets 2>/dev/null || true
    for _ in 1 2 3 4 5; do
        local remaining=""
        for pid in $targets; do
            kill -0 "$pid" 2>/dev/null && remaining="$remaining $pid"
        done
        [ -z "$remaining" ] && return 0
        sleep 1
    done
    kill -KILL $targets 2>/dev/null || true
}
mkdir -p "$RECOVERY_ROOT"

# 3. Update-Modus: Bestehende Configs sichern
IS_UPDATE=false
if [ -d "$INSTALL_DIR" ]; then
    IS_UPDATE=true
    echo ""
    echo "🔄 Bestehende Installation erkannt – starte Update-Modus."
    echo "   Deine Konfigurationen werden gesichert und danach wiederhergestellt."
    echo ""

    # payload.html und state.txt sind bewusst versionierte Startwerte, werden
    # von der laufenden Classic-Oberfläche aber fortlaufend überschrieben.
    # Sie sind kein Quellcode und dürfen ein sicheres Update nicht blockieren.
    LOCAL_CODE_CHANGES=""
    if [ -d "$INSTALL_DIR/.git" ]; then
        LOCAL_CODE_CHANGES="$(git -C "$INSTALL_DIR" status --porcelain -- . \
            ':(exclude)core/payload.html' \
            ':(exclude)core/state.txt')"
    fi
    if [ -n "$LOCAL_CODE_CHANGES" ]; then
        echo "❌ Die bestehende Installation enthält lokale Codeänderungen."
        echo "   Zum Schutz dieser Arbeit wird das Update nicht automatisch fortgesetzt."
        echo "   Sichere oder committe die Änderungen und starte den Installer danach erneut."
        exit 2
    fi

    stop_trinity_processes

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
    if [ -d "$INSTALL_DIR/.git" ]; then
        git -C "$INSTALL_DIR" bundle create "$RECOVERY_ROOT/trinity-history.bundle" --all
        git -C "$INSTALL_DIR" status -sb > "$RECOVERY_ROOT/git-status.txt"
    fi

    echo "   📁 Wiederherstellungskopie gespeichert unter: $RECOVERY_ROOT"

    # Die vorige Installation bleibt vollständig als Rückfallstand erhalten.
    mv "$INSTALL_DIR" "$ROLLBACK_DIR"
fi

# 4. Neue Version herunterladen
echo ""
echo "📥 Lade aktuelle Trinity-Version herunter..."
if command -v git &> /dev/null; then
    if ! git clone --branch main --single-branch --recurse-submodules --shallow-submodules "$REPOSITORY" "$INSTALL_DIR"; then
        [ "$IS_UPDATE" = true ] && mv "$ROLLBACK_DIR" "$INSTALL_DIR"
        echo "❌ Download fehlgeschlagen; die vorherige Installation wurde wiederhergestellt."
        exit 1
    fi
else
    [ "$IS_UPDATE" = true ] && mv "$ROLLBACK_DIR" "$INSTALL_DIR"
    echo "❌ Git fehlt. Installiere zuerst die Xcode Command Line Tools mit: xcode-select --install"
    exit 1
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
    echo "   🛟 Wiederherstellungskopie bleibt erhalten: $RECOVERY_ROOT"
fi

# 6. Virtuelle Umgebung erstellen & Pakete installieren
echo ""
echo "🐍 Erstelle virtuelle Python-Umgebung (Sandbox)..."
cd "$INSTALL_DIR" || exit
install_dependencies() {
    "$PYTHON_BIN" -m venv venv &&
    ./venv/bin/python3 -m pip install --upgrade pip -q &&
    ./venv/bin/python3 -m pip install --no-compile ".[macos]" -q
}

echo "📦 Installiere Abhängigkeiten (das kann 2–5 Minuten dauern)..."
export PYTHONIOENCODING=utf-8
if ! install_dependencies; then
    cd "$HOME"
    FAILED_DIR="$RECOVERY_ROOT/Trinity_Assistant-fehlgeschlagen"
    mv "$INSTALL_DIR" "$FAILED_DIR"
    [ "$IS_UPDATE" = true ] && mv "$ROLLBACK_DIR" "$INSTALL_DIR"
    echo "❌ Installation der Abhängigkeiten fehlgeschlagen."
    echo "   Die vorherige Installation wurde wiederhergestellt."
    echo "   Der fehlgeschlagene Stand liegt unter: $FAILED_DIR"
    exit 1
fi

# 6.4 Trinity Canvas als verwaltete Desktop-Komponente installieren.
echo "🎨 Installiere Trinity Canvas..."
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "   ⚠️  Node.js/npm fehlt. Trinity läuft, Canvas kann später mit 'trinity canvas install' ergänzt werden."
elif [ -f "$CANVAS_DIR/package.json" ]; then
    (cd "$CANVAS_DIR" && npm ci && npm run build)
    echo "   ✅ Die zu dieser Trinity-Version gehörende Canvas-Komponente ist produktionsbereit."
else
    echo "   ❌ Die eingebundene Canvas-Komponente fehlt. Prüfe die Git-Submodule."
    exit 1
fi

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

# 6.6 Inhalts-Vault und Control Plane idempotent vorbereiten
run_vault_setup() {
    if [ ! -r /dev/tty ]; then
        echo "❌ Die Vault-Ersteinrichtung benötigt ein interaktives Terminal."
        echo "   Starte danach manuell: trinity vault setup"
        return 1
    fi
    ./venv/bin/python3 trinity_cli.py --home "$INSTALL_DIR" vault setup </dev/tty
}

if [ "$IS_UPDATE" = true ]; then
    echo "🗂️  Prüfe den bereits konfigurierten Inhalts-Vault..."
    if ! ./venv/bin/python3 trinity_cli.py --home "$INSTALL_DIR" vault init; then
        echo "   Der bestehende Vault war noch nicht eindeutig konfiguriert."
        echo "   Bitte wähle jetzt den vorhandenen oder einen neuen Vault-Ordner."
        run_vault_setup
    fi
else
    echo "🗂️  Richte den Inhalts-Vault für diese Neuinstallation ein..."
    echo "   Du bestimmst selbst, wo der Vault liegen soll."
    run_vault_setup
fi

echo "🧭 Prüfe lokale MainHub-/Control-Plane-Ordner..."
./venv/bin/python3 trinity_cli.py --home "$INSTALL_DIR" control-plane init >/dev/null 2>&1 || \
    echo "   ⚠️  Control Plane konnte jetzt nicht initialisiert werden. Später möglich mit: trinity control-plane init"

# 7. Signierte lokale macOS-App erstellen. Das Hilfsskript hält das eigentliche
# Bundle unter ~/Applications und legt auf dem Desktop nur einen Verweis ab.
echo "📝 Erstelle native macOS-App..."
rm -f "$HOME/Desktop/Starte_Trinity.command"
TRINITY_APP_BACKUP_DIR="$RECOVERY_ROOT/App" ./scripts/create_app.sh
echo "🧰 Richte Trinity und die Werkstatt für den automatischen Anmeldestart ein..."
./scripts/install_autostart_mac.sh

echo ""
if [ "$IS_UPDATE" = true ]; then
    INSTALL_ACTION="Update"
else
    INSTALL_ACTION="Installation"
fi
echo "🎉 $INSTALL_ACTION erfolgreich abgeschlossen!"
echo "============================================"
echo "👉 Die native App liegt unter '$HOME/Applications/Trinity.app'."
echo "👉 Auf deinem Schreibtisch liegt ein Verweis namens 'Trinity.app'."
echo "👉 Doppelklicke einfach darauf, um Trinity zu starten."
echo "👉 Du kannst sie auch in deine Dock-Leiste ziehen."
echo "👉 In einem neuen Terminal steht außerdem der Befehl 'trinity' bereit."
echo "👉 Canvas startet mit Trinity und erscheint ohne Portangabe im Desktop-Reiter 'Canvas'."
echo "👉 Die Trinity-Werkstatt startet künftig automatisch bei deiner macOS-Anmeldung."
echo "👉 Im Browser erreichst du sie unter http://127.0.0.1:8765/#werkstatt."
if [ "$IS_UPDATE" = true ]; then
echo ""
echo "✅ Alle deine Konfigurationen (API-Keys, Soul.md, User.md, RAG, Transkripte, TrinityRuntime)"
echo "   wurden automatisch aus der alten Version übernommen."
fi
echo ""
