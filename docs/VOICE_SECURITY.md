# Voice security and privacy

- Voice binds to loopback by default. Remote bind is an explicit setting.
- Remote Realtime access requires a separate Voice token; use Tailscale or WSS.
- Do not expose ports 8765/8766 through a public router.
- Tokens belong in local configuration/Keychain, never source control or logs.
- Standard logs contain session/turn IDs and timings, not reference audio,
  complete emails or full private prompts.
- The Eve sample is not committed. Treat any clone sample as biometric/personal
  data and document authorization, purpose, retention and deletion.
- Model files and caches remain outside Git. Review upstream/model licenses.
- `DirectLLMConversationBackend` is diagnostic. Production uses Trinity Core so
  the existing approval and policy layer remains authoritative.

Before a release run a secret scan and search for machine-specific paths. Bind
tests must cover loopback, missing token and rejected unauthenticated clients.
