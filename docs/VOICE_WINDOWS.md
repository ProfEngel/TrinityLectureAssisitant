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
- Ubuntu STT URL: `http://UBUNTU_TAILSCALE_IP:8767/v1/audio/transcriptions`
  (optional; Trinity derives it automatically from the Voice URL)
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

This split also applies to Even G2 input. The glasses keep sending their audio
only to the Windows Trinity Bridge on port `8765`. With the
`eve-windows-remote` profile enabled, Windows automatically delegates that STT
request to Ubuntu's dedicated Parakeet endpoint on port `8767`; G2 does not
need a second direct connection to Ubuntu. Port `8766` remains reserved for
Eve's realtime TTS stream, so G2 input cannot consume its audio slots. If
Ubuntu is briefly unavailable, Windows falls back to local CPU Whisper for
that utterance instead of dropping it.

```text
Even G2 -> Windows Trinity :8765 -> Ubuntu Parakeet :8767 -> Windows Core
                                                              |
Windows/iOS audio output <--------- Ubuntu Eve TTS :8766 <----+
```

Relevant Windows settings:

```json
{
  "stt": {
    "companion_backend": "auto"
  },
  "voice": {
    "engine": "eve",
    "profile": "eve-windows-remote",
    "remote_voice_url": "ws://UBUNTU_TAILSCALE_IP:8766/v1/realtime",
    "remote_stt_url": "http://UBUNTU_TAILSCALE_IP:8767/v1/audio/transcriptions",
    "remote_voice_token": "THE_SAME_VOICE_TOKEN_AS_ON_UBUNTU"
  }
}
```

The Companion/G2 URL on port `8765` remains the Tailscale address of the
Windows VM. The Bridge token authenticates clients at Windows; the separate
Voice token authenticates Windows at Ubuntu.

Ubuntu setup is documented in
[VOICE_UBUNTU_HOST.md](VOICE_UBUNTU_HOST.md). Restrict ports `8766`, `8767`, `18767`
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
