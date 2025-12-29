from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


@dataclass
class Afsk1200Modulator:
    """
    AFSK1200 modulator for AX.25:
      - NRZI: data bit 0 => toggle tone, data bit 1 => keep tone
      - mark/space tones at configured frequencies
      - continuous phase across symbol boundaries
      - 16-bit signed little-endian PCM mono output
    """

    sample_rate: int
    symbol_rate: int
    frequency_mark: float
    frequency_space: float
    amplitude: float

    # State carried across calls for continuity
    _phase: float = 0.0
    _is_mark: bool = True

    def _samples_per_symbol(self) -> float:
        return self.sample_rate / float(self.symbol_rate)

    def reset(self) -> None:
        self._phase = 0.0
        self._is_mark = True

    def modulate_bits(self, bits: Iterable[int]) -> bytes:
        """
        Modulate an iterable of NRZI *data* bits into PCM.
        For AX.25 we feed the post-bitstuff stream INCLUDING flags.
        """
        import struct

        out = bytearray()
        self.modulate_bits_to(bits, out.extend)
        return bytes(out)

    def modulate_bits_to(self, bits: Iterable[int], write) -> None:
        """
        Streaming variant: calls `write(pcm_bytes)` repeatedly.
        """
        import struct

        sps = self._samples_per_symbol()
        # Handle non-integer sps by accumulating fractional error.
        frac = 0.0
        buf = bytearray()

        def flush() -> None:
            nonlocal buf
            if buf:
                write(bytes(buf))
                buf = bytearray()

        for bit in bits:
            bit = 1 if bit else 0
            if bit == 0:
                self._is_mark = not self._is_mark

            freq = self.frequency_mark if self._is_mark else self.frequency_space

            frac += sps
            n_samp = int(frac)
            frac -= n_samp

            w = 2.0 * math.pi * freq / float(self.sample_rate)
            for _ in range(n_samp):
                v = math.sin(self._phase) * float(self.amplitude)
                s = int(max(-1.0, min(1.0, v)) * 32767)
                buf += struct.pack("<h", s)
                self._phase += w
                if self._phase > 2.0 * math.pi:
                    self._phase -= 2.0 * math.pi

            # Flush periodically to avoid huge buffers.
            if len(buf) >= 65536:
                flush()

        flush()

