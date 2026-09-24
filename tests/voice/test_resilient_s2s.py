from voice.resilient_s2s import (
    prefer_shared_gpu_ggml_quantization,
    tolerate_remote_warmup,
)


def test_remote_core_warmup_is_skipped():
    class UnavailableCore:
        calls = 0

        def warmup(self):
            self.calls += 1
            raise ConnectionError("Windows is still booting")

    tolerate_remote_warmup(UnavailableCore)
    handler = UnavailableCore()

    handler.warmup()

    assert handler.calls == 0


def test_shared_gpu_ggml_uses_q8_quantization():
    observed = {}

    class FakeModel:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            observed.update(kwargs)
            return cls()

    prefer_shared_gpu_ggml_quantization(FakeModel, "Q8_0")

    FakeModel.from_pretrained("model", backend="ggml")

    assert observed["quant"] == "Q8_0"
