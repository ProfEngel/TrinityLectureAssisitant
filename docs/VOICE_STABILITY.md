# Voice stability, 2026-10-01

Trinity still uses one server-side Parakeet instance and the existing Eve
reference audio. Desktop input and output remain independently selected.

## Changes

- Persistent per-install desktop identity, shared by tray/UI and audio worker.
  Network hostname changes no longer disconnect the selected Mac speaker.
- Immediate context is limited to three minutes / 8,000 characters; extended
  transcription revisions replace their previous context entry. Permanent
  transcript and retrieved memory are not deleted. On server restart immediate
  context starts empty; durable memory remains available.
- Voice answers have a 650-token budget and 25-second HTTP read timeout.
  A superseded pending question does not publish its stale answer. An already
  running HTTP request is not actively cancelled; it finishes or times out.
- Unanswered VAD turns reopen for one second, not seven. Speech itself is not
  capped or discarded. Live recognition continues at the existing 250-ms rate.
- Linux live-caption inference uses the latest twelve seconds during long
  speech, drops speculative updates older than 750 ms and keeps update pauses
  below 500 ms. Final recognition still gets the entire utterance. This does
  not change the MLX incremental recognizer on standalone Macs.
- Two sentences are batched for synthesis; unpunctuated chunks are bounded.
- GGML clone audio is buffered per utterance and checked for nonfinite samples,
  implausible duration and codec-budget exhaustion before playback. One retry
  uses deterministic sampling with the same Eve reference; a final retry uses
  that same speaker reference without the ICL reference-text context. If all fail, audio
  is withheld rather than switching voices. This is a structural check, not a
  semantic guarantee of correct pronunciation. MLX standalone is unchanged.
- Per-device bounded outgoing queues isolate slow peers. Cumulative Parakeet
  partials supersede older waiting partials. PCM remains ordered and is never
  selectively discarded; overflowing/stalled peers disconnect and reconnect.
- Mac logs show speech detected, live partials and server audio reception.
- Follow-up fix: CoreAudio input/output callbacks share echo fingerprints
  through a lock and input uses an immutable snapshot. Concurrent playback
  previously raised `deque mutated during iteration`, aborting the input
  callback and leaving the selected Mac unable to hear further speech.
- Input-language rejection is disabled. Mixed German/English terminology and
  English input are accepted; the answer-language prompt still prefers German.

## Verification

80 automated voice, tray, writing and prompt-context tests passed after the
follow-up callback fix, including a reproduced concurrent echo-buffer change.
The third same-speaker TTS retry was also exercised on the real server: two
codec-budget failures were rejected, then the speaker-only reference succeeded
with a 2.08-second utterance generated in 0.41 seconds. End-to-end probe after
these fixes: Parakeet 0.57 seconds, LLM-to-first-audio 2.94 seconds.
The silent production probe uses the real server and saves diagnostic PCM in
`TrinityRuntime/voice/stability-probe-*.wav`, without playing on user devices.
Run `venv/bin/python tools/probe_voice_stability.py` from the Mac checkout when
no conversation is in progress. It temporarily selects a diagnostic input and
output, then restores this Mac. Do not run while someone uses another client.

Measured on 2026-10-01: first validated TTS audio after 0.49–1.32 seconds for
three short utterances; Parakeet roundtrip 0.39 seconds for already supplied
audio; complete new LLM question to first Eve audio 2.94 seconds. These are
individual measurements, not guarantees under GPU or network load. Live
microphone end-of-speech detection adds ~420 ms plus network transport.

## User acceptance test

### Confirmed TextEdit state (follow-up)

The server previously muted conversational requests immediately upon recognizing
“ich diktiere jetzt”, even when the Mac rejected the start due to focus or
permissions. A failed stop recognition could leave this server-only state on
indefinitely. This looked like switching window sharing killed the assistant.

Now the selected, allowlisted Mac confirms the editor state through the existing
audio-input API (`action=textedit_state`). A private, short-lived editor lease
expires after 15 seconds, is bound to the input-selection epoch and is renewed
by the Mac UI. It stops if the target loses focus or another microphone is
selected. A failed start never enables suppression. “Trinity, stopp” is an
additional dictation stop command. This endpoint does not change input/output
selection or persistent configuration.

93 focused tests passed after this change. The production synthetic-window
probe recognized TRINITY / 42 from a 1600×1000 image and delivered first audio
after 3.6 seconds. Local window capture took 0.35 seconds; no private screenshot
was sent for this synthetic probe. Window sharing defaults off after app restart.

1. On MiniTrinity select both “Hier auf dem Mac zuhören” and “Hier auf dem Mac
   antworten”. In Lecture mode say “Trinity, hörst du mich?”; Office mode does
   not require a wakeword.
2. Speak for 30–60 seconds at normal/fast pace, then say “Trinity, fasse das in
   zwei Sätzen zusammen.” Check relevance, delay and lack of acoustic feedback.
3. Switch input/output to iPad/iPhone/G2 and back. The G2 remains input-only.
4. In TextEdit test “Trinity, ich diktiere jetzt”, a sentence, then
   “Trinity, Diktat beenden”. Editing still requires the existing Accessibility
   permission and a verified TextEdit target.

Server source/config backups are under `TrinityRuntime/backups/stability-20261001`
and `core/config.json.pre-stability-*`. No iOS or G2 rebuild is required for
these server-side changes. The Mac must run the updated desktop checkout.
