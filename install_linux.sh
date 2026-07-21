#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${TRINITY_HOME:-$HOME/Trinity_Assistant}"
REPOSITORY="https://github.com/ProfEngel/TrinityLectureAssisitant.git"

command -v python3 >/dev/null || { echo "Python 3 fehlt."; exit 1; }
python3 - <<'PY'
import sys
if not ((3, 10) <= sys.version_info[:2] < (3, 15)):
    raise SystemExit("Trinity benoetigt Python 3.10 bis 3.14.")
PY

BACKUP="${INSTALL_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
IS_UPDATE=false
if [ -d "$INSTALL_DIR" ]; then
    IS_UPDATE=true
    mkdir -p "$BACKUP"
    for item in core/config.json core/Soul.md core/User.md memory RAG gen_images; do
        [ -e "$INSTALL_DIR/$item" ] && cp -a "$INSTALL_DIR/$item" "$BACKUP/"
    done
    rm -rf "$INSTALL_DIR"
fi

if command -v git >/dev/null; then
    git clone --branch main --single-branch "$REPOSITORY" "$INSTALL_DIR"
else
    echo "Bitte git installieren oder das Repository manuell nach $INSTALL_DIR klonen."
    exit 1
fi

if [ -d "$BACKUP" ]; then
    for item in config.json Soul.md User.md; do
        [ -f "$BACKUP/core/$item" ] && cp "$BACKUP/core/$item" "$INSTALL_DIR/core/$item"
    done
    for item in memory RAG gen_images; do
        [ -d "$BACKUP/$item" ] && mkdir -p "$INSTALL_DIR/$item" && cp -a "$BACKUP/$item/." "$INSTALL_DIR/$item/"
    done
    rm -rf "$BACKUP"
fi

python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/python" -m pip install --upgrade pip
"$INSTALL_DIR/venv/bin/python" -m pip install --no-compile ".[linux]"
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/trinity" <<EOF
#!/bin/sh
exec "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/trinity_cli.py" "\$@"
EOF
chmod +x "$HOME/.local/bin/trinity"
run_vault_setup() {
    if [ ! -r /dev/tty ]; then
        echo "Die Vault-Ersteinrichtung benötigt ein interaktives Terminal."
        echo "Starte danach manuell: $HOME/.local/bin/trinity vault setup"
        return 1
    fi
    "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/trinity_cli.py" --home "$INSTALL_DIR" vault setup </dev/tty
}
if [ "$IS_UPDATE" = true ]; then
    echo "Pruefe den bereits konfigurierten Inhalts-Vault ..."
    "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/trinity_cli.py" --home "$INSTALL_DIR" vault init || \
        run_vault_setup
else
    echo "Richte den Inhalts-Vault fuer diese Neuinstallation ein ..."
    echo "Du bestimmst selbst, wo der Vault liegen soll."
    run_vault_setup
fi
"$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/trinity_cli.py" --home "$INSTALL_DIR" control-plane init >/dev/null || true
echo "Installation fertig. Starte mit: $HOME/.local/bin/trinity onboarding"
echo "Danach: $HOME/.local/bin/trinity server --host 127.0.0.1 --port 8765"
