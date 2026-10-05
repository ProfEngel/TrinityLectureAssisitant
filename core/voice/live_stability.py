"""Keep live captions current even during long, uninterrupted speech.

Only speculative/live processing uses the rolling audio window. Final
transcription continues to receive the COMPLETE recording.
"""


def recent_audio(audio, sample_rate=16000, seconds=12):
    return audio[-int(sample_rate * seconds):]


def install_live_stability():
    from speech_to_speech.STT.parakeet_tdt_handler import ParakeetTDTSTTHandler as ParakeetTDTHandler
    from speech_to_speech.VAD.vad_handler import VADHandler

    if getattr(ParakeetTDTHandler, "_trinity_live_guard", False):
        return
    original_process = ParakeetTDTHandler.process
    original_show = ParakeetTDTHandler._show_progressive_transcription
    original_pause = VADHandler._progressive_processing_pause

    def process(self, audio):
        if audio.mode == "progressive" and self._item_age_s(audio) > 0.75:
            return  # Ignore old captions, NEVER final speech.
        yield from original_process(self, audio)

    def show(self, audio):
        if self.backend == "nano_parakeet" and len(audio) > 16000 * 12:
            # The incremental helper maintains sample offsets. Reset before
            # changing its coordinate system to the recent audio window.
            self.streaming_handler.reset()
            audio = recent_audio(audio)
        return original_show(self, audio)

    def pause(self, duration_ms):
        # Upstream increases to 1.5s during long speech. The rolling STT window
        # keeps inference bounded, so retain the short update interval.
        return min(original_pause(self, duration_ms), 0.5)

    ParakeetTDTHandler.process = process
    ParakeetTDTHandler._show_progressive_transcription = show
    VADHandler._progressive_processing_pause = pause
    ParakeetTDTHandler._trinity_live_guard = True
