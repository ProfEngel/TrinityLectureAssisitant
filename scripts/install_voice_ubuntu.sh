#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/venv/bin/python"
VOICE_DIR="$ROOT/TrinityRuntime/voices/eve"
VOICE_SOURCE="${1:-}"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This installer is intended for the Ubuntu GPU host." >&2
  exit 1
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "Trinity Python environment not found: $PYTHON" >&2
  exit 1
fi
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "NVIDIA driver not found. Install and verify it on Ubuntu first." >&2
  exit 1
fi

nvidia-smi >/dev/null
"$PYTHON" -m pip install "speech-to-speech==0.2.11" "websockets>=14,<18"

mkdir -p "$VOICE_DIR"
cp "$ROOT/assets/voices/eve/ref_text.txt" "$VOICE_DIR/ref_text.txt"
if [[ -n "$VOICE_SOURCE" ]]; then
  if [[ ! -f "$VOICE_SOURCE" ]]; then
    echo "Voice sample not found: $VOICE_SOURCE" >&2
    exit 1
  fi
  cp "$VOICE_SOURCE" "$VOICE_DIR/Eve_Schule.mp3"
else
  echo "No authorized Eve sample copied. Pass its path as the first argument." >&2
fi

cat <<'EOF'
Ubuntu Eve dependencies are installed.

Next configure Trinity's voice section with:
  profile: eve-linux-gpu-server
  access_token: a long Voice token
  remote_core_base_url: http://WINDOWS-TAILSCALE-IP:18767/v1
  remote_core_api_key: the separate Windows Core token

Then run:
  venv/bin/trinity voice doctor --profile eve-linux-gpu-server
  venv/bin/trinity voice serve --profile eve-linux-gpu-server

Do not expose ports 8766 or 18767 through a public router.
EOF
