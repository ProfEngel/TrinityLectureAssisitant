# Voice troubleshooting

Start with:

```bash
trinity voice doctor --profile eve-mac-local
```

| Symptom | Check |
|---|---|
| Eve sample missing | Install it locally and verify `voice.reference_audio`. |
| Models load slowly | First use downloads/cache-warms models; do not start during a lecture. |
| Audio stutters | Increase prebuffer/chunk size, reduce competing MLX load, use a faster conversation model. |
| Response too slow | Benchmark Trinity and direct profiles separately; keep first spoken answer short. |
| Companion rejected | Match Voice port and token; Bridge token alone is not sufficient. |
| Remote connection fails | Check Tailscale, bind host, firewall and that port 8766 is listening. |
| Windows has no useful TTS | Verify NVIDIA/CUDA and choose a compatible Qwen3-TTS Base checkpoint. |
| Voice process exits | With fallback enabled Trinity resumes Legacy; inspect the Voice log before retrying. |
| Eve repeats reference ending | Verify transcript/audio pairing; enable conservative start-segment handling instead of hard trimming. |
| Trinity hears itself | Use headphones, cancel playback on barge-in and ensure only one engine owns the microphone. |
| Speaking does not interrupt Eve | Use a local/server Realtime profile, enable barge-in, and test with headphones before lowering the threshold. Old local profiles are migrated automatically in v0.17.0. |
| iPhone/iPad cannot connect | Use port 8766, the Voice token (not merely the Bridge token), a server profile and a Tailscale-reachable bind/firewall. |
| Eve on a Windows VM is unusably slow | Verify that `nvidia-smi` works inside the VM; otherwise keep Legacy on Windows or run Eve on a GPU-capable Trinity host. |

Stop the standalone runtime with `Ctrl+C`. In the normal launcher, changing the
engine requires restarting Trinity because microphone ownership changes.
