# iPhone and iPad Voice Companion

The Companion remains a thin client: microphone capture, optional level display,
PCM streaming, live transcript, Trinity text, streamed audio and cancellation.
Parakeet, Qwen and the LLM stay on the configured Mac or Windows server.

1. Start `eve-mac-server` or `eve-windows-server` on the Trinity machine.
2. Use the machine's Tailscale address and voice port `8766` in the matching
   Companion connection profile.
3. Enter the same Voice token. Tokens are stored in the device Keychain.
4. Select **Realtime Eve** in Voice settings and begin with Push-to-Talk.
5. Switch to **Legacy Companion STT/TTS** immediately if realtime is unavailable.

Input is PCM signed 16-bit mono at 16 kHz unless server negotiation reports a
different format. Output honors event metadata rather than assuming that input
and output sample rates match. The client reconnects with bounded exponential
backoff and discards audio belonging to cancelled or stale turns.

iOS cannot promise indefinite background microphone operation. Foreground and
Push-to-Talk are the reliable baseline; route changes, calls and app suspension
can interrupt a voice session.
