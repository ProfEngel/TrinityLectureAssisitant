from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np

from core.voice.device_identity import desktop_device_id
from core.voice.recent_context import RecentVoiceContext
from core.voice.tts_safety import checked_clone_chunks
from core.voice.language_policy import segment_for_speech
from core.voice.live_stability import recent_audio


def test_upstream_timeout_localized_without_altering_turn_metadata(monkeypatch):
    import sys
    from types import ModuleType
    from core.voice.upstream_entrypoint import install_german_timeout_message
    class Chunk:
        text = "Wow I'm a bit slow today, could you repeat that?"
        turn_id = 'turn-123'
        def model_copy(self, *, update):
            return SimpleNamespace(text=update['text'], turn_id=self.turn_id)
    tail = object()
    class Handler:
        def _generate(self, *args, **kwargs):
            yield Chunk()
            yield tail
    fake = ModuleType('speech_to_speech.LLM.base_openai_compatible_language_model')
    fake.BaseOpenAICompatibleHandler = Handler
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    install_german_timeout_message()
    install_german_timeout_message()  # idempotent installation
    chunks = list(Handler()._generate())
    assert chunks[0].text.startswith('Das Modell antwortet')
    assert chunks[0].turn_id == 'turn-123'
    assert chunks[1] is tail


def test_transport_history_evicts_without_invoking_memory_compactor(monkeypatch):
    import sys
    from types import ModuleType
    from core.voice.upstream_entrypoint import install_trinity_history_guard
    class Chat:
        size = 30
        def trim_if_needed(self, compactor=None):
            self.called_with = compactor
    fake = ModuleType("speech_to_speech.LLM.chat")
    fake.Chat = Chat
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    install_trinity_history_guard()
    chat = Chat()
    chat.trim_if_needed(lambda _: (_ for _ in ()).throw(AssertionError("must not summarize")))
    assert chat.called_with is None
    assert chat.size == 6


def test_identity_shared_by_simultaneously_starting_clients(tmp_path):
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: desktop_device_id(tmp_path, "PRIVAT"), range(30)))
    assert len(set(ids)) == 1
    assert desktop_device_id(tmp_path, "privat") == ids[0]


def test_context_replaces_revisions_and_expires():
    now = [0]
    context = RecentVoiceContext(max_chars=90, max_age=180, clock=lambda: now[0])
    context.append("User", "Das ist")
    now[0] = 1
    context.append("User", "Das ist eine Tabelle.")
    assert context.render().count("Das ist") == 1
    for i in range(100):
        context.append("User", f"Satz Nummer {i}")
    assert len(context.render()) <= 90
    now[0] = 190
    assert not context.render()


def test_live_audio_is_bounded_without_changing_original():
    audio = np.arange(30 * 16000)
    window = recent_audio(audio)
    assert len(window) == 12 * 16000
    assert window[-1] == audio[-1]
    assert len(audio) == 30 * 16000


def test_live_guard_drops_stale_partials_but_never_final(monkeypatch):
    import sys
    import types
    from core.voice.live_stability import install_live_stability
    class STT:
        backend = "nano_parakeet"
        streaming_handler = SimpleNamespace(reset=lambda: None)
        def _item_age_s(self, item):
            return item.age
        def process(self, item):
            yield item
        def _show_progressive_transcription(self, audio):
            return len(audio)
    class VAD:
        def _progressive_processing_pause(self, duration):
            return 1.5
    stt_module = types.ModuleType("speech_to_speech.STT.parakeet_tdt_handler")
    stt_module.ParakeetTDTSTTHandler = STT
    vad_module = types.ModuleType("speech_to_speech.VAD.vad_handler")
    vad_module.VADHandler = VAD
    monkeypatch.setitem(sys.modules, stt_module.__name__, stt_module)
    monkeypatch.setitem(sys.modules, vad_module.__name__, vad_module)
    install_live_stability()
    handler = STT()
    old = SimpleNamespace(mode="progressive", age=2)
    assert list(handler.process(old)) == []
    old.mode = "final"
    assert list(handler.process(old)) == [old]
    assert handler._show_progressive_transcription(np.zeros(16000 * 40)) == 16000 * 12
    assert VAD()._progressive_processing_pause(40000) == 0.5


def test_bad_audio_never_leaks_and_deterministic_retry_preserves_reference():
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        duration = 15 if kwargs["do_sample"] else 2
        yield np.zeros(duration * 100), 100, {}

    handler = SimpleNamespace(
        model=SimpleNamespace(generate_voice_clone_streaming=generate),
        language="German", ref_audio="eve.wav", ref_text="Eve reference",
        xvec_only=False, streaming_chunk_size=8, parity_mode=False,
        non_streaming_mode=True, cancel_scope=None,
        _estimate_max_new_tokens=lambda text: 360,
        _stream=lambda chunks, **kwargs: chunks,
    )
    chunks = list(checked_clone_chunks(handler, "Hallo."))
    assert len(chunks) == 1 and chunks[0][0].size == 200
    assert len(calls) == 2 and calls[1]["do_sample"] is False
    assert all(call["ref_audio"] == "eve.wav" for call in calls)


def test_unpunctuated_speech_chunks_are_bounded():
    text = " ".join(["Tabelle"] * 100)
    chunks = segment_for_speech(text)
    assert all(len(chunk) <= 280 for chunk in chunks)
    assert " ".join(chunks) == text


def test_final_tts_retry_uses_same_speaker_without_reference_text_context():
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        duration = 2 if kwargs["xvec_only"] else 15
        yield np.zeros(duration * 100), 100, {}
    handler = SimpleNamespace(
        model=SimpleNamespace(generate_voice_clone_streaming=generate),
        language="German", ref_audio="eve.wav", ref_text="Eve reference",
        xvec_only=False, streaming_chunk_size=8, parity_mode=False,
        non_streaming_mode=True, cancel_scope=None,
        _estimate_max_new_tokens=lambda text: 360,
        _stream=lambda chunks, **kwargs: chunks,
    )
    chunks = list(checked_clone_chunks(handler, "Hallo."))
    assert len(chunks) == 1 and chunks[0][0].size == 200
    assert len(calls) == 3 and calls[-1]["xvec_only"]
    assert all(call["ref_audio"] == "eve.wav" for call in calls)


def test_slow_peer_cannot_block_other_peer(tmp_path):
    import asyncio
    import json
    from core.voice.transport.multiplex_proxy import MultiplexingVoiceRouter

    async def run():
        delivered = []
        blocked = asyncio.Event()
        class Peer:
            def __init__(self, slow=False):
                self.slow = slow
            async def send(self, raw):
                if self.slow:
                    await blocked.wait()
                else:
                    delivered.append(json.loads(raw))
            async def close(self, **kwargs):
                pass
        router = MultiplexingVoiceRouter("localhost", 1, 2, [], tmp_path / "config.json")
        slow, fast = Peer(True), Peer()
        for peer in (slow, fast):
            for i in range(40):
                router._enqueue(peer, json.dumps({"type": "conversation.item.input_audio_transcription.partial",
                                                  "item_id": "turn", "transcript": str(i)}))
        await asyncio.sleep(0.02)
        assert delivered[-1]["transcript"] == "39"
        assert len(delivered) == 1
        router._drop_outbox(slow)
        router._drop_outbox(fast)
    asyncio.run(run())
