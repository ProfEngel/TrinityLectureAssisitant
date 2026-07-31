# Eve Voice on Windows 11

Windows supports both a local desktop conversation and a headless Voice Gateway
for iPhone/iPad. Both require a compatible NVIDIA GPU visible inside Windows and
a CUDA/PyTorch Qwen3-TTS Base checkpoint. A VM therefore needs working GPU
passthrough; CPU-only synthesis is not a productive Eve configuration. The
checkpoint is configurable because the Apple MLX identifier is not portable.

```powershell
cd $env:LOCALAPPDATA\Trinity
.\scripts\install_voice_windows.ps1 -VoiceSource "C:\private\Eve_Schule.mp3"
trinity voice doctor --profile eve-windows-server
trinity voice serve --profile eve-windows-server
```

For microphone and speakers on the Windows machine use:

```powershell
trinity voice doctor --profile eve-windows-local
trinity voice serve --profile eve-windows-local
```

The local profile uses the same realtime barge-in path as macOS: new speech
cancels the active response and flushes buffered Eve audio.

Keep the bind host at `127.0.0.1` for local validation. For Tailscale clients,
select the server profile, configure a separate Voice token, and if needed
create the private firewall rule with `-OpenFirewall`. In the Companion enter
`ws://TAILSCALE-IP:8766/v1/realtime` and the same Voice token. Never forward
port 8766 from a public router.

If CUDA, the selected checkpoint or synthesis performance is unsuitable, choose
the **Legacy** engine. Existing Windows SAPI and optional Whisper remain intact.
