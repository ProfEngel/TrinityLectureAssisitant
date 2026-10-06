"""First-run model loading and warmup; no network to the user's LLM."""
import argparse
import json
import sys
from pathlib import Path
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    from core.voice.config import load_voice_config
    raw = json.loads(args.config.read_text(encoding="utf-8"))
    config = load_voice_config(Path(__file__).resolve().parents[1], raw)
    errors = config.validate()
    if errors:
        raise RuntimeError("; ".join(errors))
    from core.voice.offline_startup import install_cached_vad_loader
    install_cached_vad_loader()
    import torch
    torch.hub.load("snakers4/silero-vad", "silero_vad", trust_repo=True)
    from speech_to_speech.STT.parakeet_tdt_handler import ParakeetTDTSTTHandler
    stt = ParakeetTDTSTTHandler.__new__(ParakeetTDTSTTHandler)
    stt.setup(model_name=config.profile.stt_model, device=config.profile.device, language="de")
    print("Parakeet geladen und Warmup abgeschlossen.", flush=True)
    del stt
    import gc
    gc.collect()
    if config.profile.device == "cuda":
        torch.cuda.empty_cache()
    from speech_to_speech.TTS.qwen3_tts_handler import Qwen3TTSHandler
    tts = Qwen3TTSHandler.__new__(Qwen3TTSHandler)
    clone = "customvoice" not in config.profile.tts_model.lower()
    tts.setup(should_listen=Event(), model_name=config.profile.tts_model, device=config.profile.device,
              backend=config.profile.tts_backend, language="German", speaker=config.tts_speaker or "Vivian",
              ref_audio=str(config.reference_audio) if clone else None, ref_text=config.reference_text,
              streaming_chunk_size=config.streaming_chunk_size,
              mlx_quantization="4bit" if config.profile.device == "mps" else None)
    print("Qwen3 geladen und Warmup abgeschlossen. Keine zusätzliche STT-Instanz im späteren Betrieb.", flush=True)

if __name__ == "__main__":
    main()
