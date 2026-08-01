# Eve Voice on Windows 11

Windows supports two production layouts:

1. **Recommended for a VM:** Windows runs Trinity's UI, sessions, memory,
   agents and policy layer. A private Ubuntu host with an NVIDIA GPU runs
   Parakeet STT and Qwen3-TTS/Eve. No PCI passthrough is required.
2. **Native Windows GPU:** Windows runs Trinity and the CUDA voice models on a
   GPU that is directly visible inside Windows.

## Windows VM with an Ubuntu GPU host

Run in an elevated PowerShell:

```powershell
cd $env:LOCALAPPDATA\Trinity
.\scripts\install_voice_windows.ps1 -RemoteGPUClient -OpenFirewall
```

In **Settings -> Voice**, select
`Windows VM with Eve on an Ubuntu GPU host` and configure:

- Ubuntu Voice URL: `ws://UBUNTU_TAILSCALE_IP:8766/v1/realtime`
- Voice token: a long, random token shared only with Ubuntu
- Windows Core bind: `0.0.0.0`
- Windows Core port: `18767`
- Windows Core token: a second long, random token shared only with Ubuntu

The normal Trinity LLM provider can point to an OpenAI-compatible endpoint on
Ubuntu, for example `http://UBUNTU_TAILSCALE_IP:1234/v1`. Restart Trinity and
run:

```powershell
trinity voice doctor --profile eve-windows-remote
```

Ubuntu setup is documented in
[VOICE_UBUNTU_HOST.md](VOICE_UBUNTU_HOST.md). Restrict ports `8766`, `18767`
and the LLM port to the private LAN/Tailnet. Do not expose them on a public
router.

## Native Windows GPU

Native Windows voice requires a compatible NVIDIA GPU visible inside Windows
and a CUDA/PyTorch Qwen3-TTS Base checkpoint. The checkpoint is configurable
because the Apple MLX identifier is not portable.

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
`ws://TAILSCALE-IP:8766/v1/realtime` and either that Voice token or the existing
Companion Bridge token. Never forward
port 8766 from a public router.

If CUDA, the selected checkpoint or synthesis performance is unsuitable, choose
the **Legacy** engine. Existing Windows SAPI and optional Whisper remain intact.
