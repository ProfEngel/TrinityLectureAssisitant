"""Wire-format validation for realtime voice audio."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PCMFormat:
    sample_rate: int = 16_000
    channels: int = 1
    sample_width: int = 2

    @property
    def bytes_per_second(self) -> int:
        return self.sample_rate * self.channels * self.sample_width

    def validate(self, data: bytes) -> None:
        if self.sample_rate != 16_000 or self.channels != 1 or self.sample_width != 2:
            raise ValueError("Der Voice-Eingang erwartet PCM16 Mono mit 16 kHz.")
        if len(data) % self.sample_width:
            raise ValueError("PCM16-Audio muss eine gerade Byteanzahl haben.")
