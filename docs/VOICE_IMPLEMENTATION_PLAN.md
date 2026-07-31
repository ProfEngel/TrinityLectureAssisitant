# Trinity Eve Voice Runtime: implementation plan

## Baseline and rollback

The existing Faster-Whisper/native STT and macOS `say`/Windows SAPI path remains
the default `legacy` engine. Eve is an opt-in engine and can automatically fall
back to Legacy if its process fails. Before implementation, Desktop, Companion
and G2 sources were frozen with Git bundles, local patches, untracked archives
and SHA-256 checksums.

## Integration

1. Keep Trinity Core text-first and expose it as a local OpenAI-compatible
   conversation adapter.
2. Run the pinned upstream `speech-to-speech` pipeline as a separate process for
   VAD, German Parakeet STT and streaming Qwen3-TTS.
3. Put an authenticated WebSocket proxy in front of upstream Realtime mode.
4. Add `legacy`/`eve`, platform profiles, doctor and benchmark commands.
5. Extend the existing iOS/iPadOS Companion as a thin PCM streaming client.
6. Keep the voice sample local and document its exact transcript and metadata.

## Risks and gates

- MLX memory contention: separate process, short first response and interruptible
  playback; benchmark on the actual machine.
- Audio route changes on iOS: Push-to-Talk first, explicit interruption handling.
- Remote exposure: loopback default, explicit bind plus token and Tailscale.
- Windows Qwen checkpoint compatibility: configurable model, CUDA validation and
  documented Legacy fallback.
- Gate: unit/integration tests, macOS smoke test, Windows technical validation,
  iOS build, secret scan and hard-coded path scan.
