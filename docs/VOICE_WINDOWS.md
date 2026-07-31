# Eve Voice on Windows 11

The Windows profile is primarily a headless Voice Gateway for iPhone/iPad. It
requires a compatible NVIDIA GPU and a CUDA/PyTorch Qwen3-TTS Base checkpoint.
The checkpoint is configurable because the Apple MLX identifier is not portable.

```powershell
cd $env:LOCALAPPDATA\Trinity
.\scripts\install_voice_windows.ps1 -VoiceSource "C:\private\Eve_Schule.mp3"
trinity voice doctor --profile eve-windows-server
trinity voice serve --profile eve-windows-server
```

Keep the bind host at `127.0.0.1` for local validation. For Tailscale clients,
explicitly select `0.0.0.0`, configure a token, and if needed create the private
firewall rule with `-OpenFirewall`. Never forward port 8766 from a public router.

If CUDA, the selected checkpoint or synthesis performance is unsuitable, choose
the **Legacy** engine. Existing Windows SAPI and optional Whisper remain intact.
