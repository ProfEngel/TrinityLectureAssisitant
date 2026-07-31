# Eve Voice on macOS

Requirements: Apple Silicon, an installed Trinity environment, sufficient free
memory and an authorized local Eve reference sample.

```bash
cd /path/to/Trinity
./scripts/install_voice_macos.sh /path/to/Eve_Schule.mp3
venv/bin/trinity voice doctor --profile eve-mac-local
venv/bin/trinity voice serve --profile eve-mac-local
```

The installer does not enable Eve. Select **Einstellungen > Sprache > Trinity
Voice Runtime > Eve** only after `doctor` passes. Select **Legacy** at any time to
return to the previous STT/TTS path. If automatic fallback is enabled, a failed
Eve process releases the microphone and Trinity restarts Legacy STT.

For a Companion server, choose `eve-mac-server`, set a long token, bind to
`0.0.0.0` only inside a trusted Tailscale/private network, then restart Trinity.

```bash
venv/bin/trinity voice benchmark --profile eve-mac-local --rounds 3
```

The benchmark measures the conversation path. Record cold model load, final STT
to first token, TTS first chunk and end-to-audible latency separately during the
live smoke test; machine load materially changes these values.
