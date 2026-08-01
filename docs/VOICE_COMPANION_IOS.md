# iPhone and iPad Voice Companion

The Companion remains a thin client: microphone capture, optional level display,
PCM streaming, live transcript, Trinity text, streamed audio and cancellation.
Parakeet, Qwen and the LLM stay on the configured Mac or Windows server.

1. Start `eve-mac-server` or `eve-windows-server` on the Trinity machine.
2. Use the machine's Tailscale address and voice port `8766` in the matching
   Companion connection profile.
3. Enter the Companion Bridge token, or a deliberately separate Voice token.
   Tokens are stored in the device Keychain.
4. Select **Realtime Eve vom Server** in Voice settings and start listening.
5. Switch to **Legacy Companion STT/TTS** immediately if realtime is unavailable.

The protected Voice port accepts the existing Bridge token and, when configured,
a separate Voice token. This keeps simple setups consistent while still
allowing strict token separation. The default
Voice URL is derived from the selected Bridge profile by replacing the port
with `8766`; it can be overridden per Work/Private/Test connection profile.

Realtime profiles provide two concurrent session slots by default so local
desktop Eve and one Companion conversation can remain active together.

Input is PCM signed 16-bit mono at 16 kHz unless server negotiation reports a
different format. Output honors event metadata rather than assuming that input
and output sample rates match. The client reconnects with bounded exponential
backoff and discards audio belonging to cancelled or stale turns.

The app runs `AVAudioSession` in `voiceChat` mode so iOS/iPadOS applies acoustic
echo cancellation. Speaking while Eve answers causes server-side barge-in and
immediately clears local playback. The visible stop action and a face swipe also
cancel the current Eve response without ending the listening session.

iOS cannot promise indefinite background microphone operation. Foreground and
Push-to-Talk are the reliable baseline; route changes, calls and app suspension
can interrupt a voice session.
