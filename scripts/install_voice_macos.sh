#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${TRINITY_PYTHON:-$ROOT/venv/bin/python}"
VOICE_SOURCE="${1:-${TRINITY_EVE_VOICE_SOURCE:-}}"
RUNTIME="${TRINITY_RUNTIME_DIR:-$ROOT/TrinityRuntime}"
VOICE_DIR="$RUNTIME/voices/eve"

if [[ "$(uname -s)" != "Darwin" ]] || [[ "$(uname -m)" != "arm64" ]]; then
  echo "Eve MLX requires an Apple-Silicon Mac." >&2
  exit 1
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment not found: $PYTHON" >&2
  echo "Install Trinity first or set TRINITY_PYTHON." >&2
  exit 1
fi

if "$PYTHON" -m pip --version >/dev/null 2>&1; then
  "$PYTHON" -m pip install "speech-to-speech==0.2.11" "mlx-audio==0.4.2" "websockets>=14,<18"
elif command -v uv >/dev/null 2>&1; then
  uv pip install --python "$PYTHON" "speech-to-speech==0.2.11" "mlx-audio==0.4.2" "websockets>=14,<18"
else
  echo "Neither pip in the selected Python environment nor uv was found." >&2
  exit 1
fi
mkdir -p "$VOICE_DIR"
cp "$ROOT/assets/voices/eve/ref_text.txt" "$VOICE_DIR/ref_text.txt"
if [[ -n "$VOICE_SOURCE" ]]; then
  [[ -f "$VOICE_SOURCE" ]] || { echo "Voice sample not found: $VOICE_SOURCE" >&2; exit 1; }
  cp "$VOICE_SOURCE" "$VOICE_DIR/Eve_Schule.mp3"
else
  echo "No voice sample copied. Pass its authorized local path as argument 1."
fi

echo "Eve dependencies installed. Trinity still uses the Legacy voice engine."
echo "Voice directory: $VOICE_DIR"
echo "Next: $ROOT/venv/bin/trinity voice doctor --profile eve-mac-local"
