import math
from typing import Iterable, List


def bytes_to_bits(data: bytes) -> List[int]:
    bits: List[int] = []
    for b in data:
        for i in range(8):
            bits.append((b >> (7 - i)) & 1)
    return bits


def generate_tone(
    frequency: float,
    duration_s: float,
    sample_rate: int,
    amplitude: float,
) -> bytes:
    """
    Generate a simple 16-bit mono PCM sine wave.
    """
    import struct

    num_samples = int(duration_s * sample_rate)
    samples = []
    for n in range(num_samples):
        t = n / sample_rate
        value = amplitude * math.sin(2 * math.pi * frequency * t)
        # 16-bit signed PCM
        s = int(max(-1.0, min(1.0, value)) * 32767)
        samples.append(struct.pack("<h", s))
    return b"".join(samples)


def encode_bits_to_pcm(
    bits: Iterable[int],
    sample_rate: int,
    symbol_rate: int,
    frequency_mark: float,
    frequency_space: float,
    amplitude: float,
    pre_tone_ms: int = 0,
    post_tone_ms: int = 0,
) -> bytes:
    """
    Very simple BFSK-style encoder:
    - '1' => frequency_mark
    - '0' => frequency_space
    """

    bit_duration_s = 1.0 / symbol_rate
    pcm_chunks: List[bytes] = []

    # Pre-tone
    if pre_tone_ms > 0:
        pcm_chunks.append(
            generate_tone(
                frequency_mark,
                pre_tone_ms / 1000.0,
                sample_rate,
                amplitude,
            )
        )

    for bit in bits:
        freq = frequency_mark if bit else frequency_space
        pcm_chunks.append(
            generate_tone(freq, bit_duration_s, sample_rate, amplitude)
        )

    # Post-tone
    if post_tone_ms > 0:
        pcm_chunks.append(
            generate_tone(
                frequency_mark,
                post_tone_ms / 1000.0,
                sample_rate,
                amplitude,
            )
        )

    return b"".join(pcm_chunks)


