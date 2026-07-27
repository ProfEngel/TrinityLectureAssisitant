#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="de.profengel.trinity"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$LABEL.plist"
LOG_DIR="$PROJECT_DIR/logs"
PYTHON_PATH="$PROJECT_DIR/venv/bin/python3"
LAUNCHER_PATH="$PROJECT_DIR/trinity_launcher.py"

if [ ! -x "$PYTHON_PATH" ] || [ ! -f "$LAUNCHER_PATH" ]; then
    echo "❌ Trinity-Autostart kann erst nach der Installation eingerichtet werden."
    exit 1
fi

mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR"
cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_PATH</string>
    <string>$LAUNCHER_PATH</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$PROJECT_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$HOME/.local/bin:$HOME/.opencode/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>ProcessType</key>
  <string>Interactive</string>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/login-start.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/login-start-error.log</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST_PATH" >/dev/null
launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
echo "✅ Trinity startet künftig bei der Anmeldung; die Werkstatt ist dadurch automatisch verfügbar."
