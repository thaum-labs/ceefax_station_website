import os
import sys
import wave

from .audio_encoder import bytes_to_bits, encode_bits_to_pcm
from .compiler import Page
from .config import AppConfig


class AudioTransmitter:
    """
    Simple transmitter that writes per-page WAV files to disk.
    You can then:
      - play them with `aplay out/page_100.wav`
      - feed them into a VOX-triggered transmitter
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.output_mode = getattr(self.config.audio, "output", "files").lower()
        if self.output_mode in ("files", "both"):
            os.makedirs(self.config.general.output_dir, exist_ok=True)

    def _frame_to_wav_path(self, page: Page) -> str:
        filename = f"page_{page.page_id.replace('.', '_')}.wav"
        return os.path.join(self.config.general.output_dir, filename)

    def transmit_page(self, page: Page, frame: bytes):
        audio_cfg = self.config.audio

        bits = bytes_to_bits(frame)
        pcm = encode_bits_to_pcm(
            bits=bits,
            sample_rate=audio_cfg.sample_rate,
            symbol_rate=audio_cfg.symbol_rate,
            frequency_mark=audio_cfg.frequency_mark,
            frequency_space=audio_cfg.frequency_space,
            amplitude=audio_cfg.amplitude,
            pre_tone_ms=audio_cfg.pre_tone_ms,
            post_tone_ms=audio_cfg.post_tone_ms,
        )

        if self.output_mode in ("files", "both"):
            path = self._frame_to_wav_path(page)
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(audio_cfg.sample_rate)
                wf.writeframes(pcm)

            print(f"[AUDIO] Wrote WAV for page {page.page_id} -> {path}")
        if self.output_mode in ("stdout", "both"):
            # Stream raw 16-bit PCM to stdout for use with e.g.:
            #   python -m src.main | aplay -f S16_LE -c 1 -r 48000
            sys.stdout.buffer.write(pcm)
            sys.stdout.buffer.flush()
            print(f"[AUDIO] Streamed page {page.page_id} to stdout", file=sys.stderr)
        elif self.output_mode not in ("files", "stdout", "both"):
            raise ValueError(f"Unknown audio output mode: {self.output_mode}")


class Ax25Transmitter:
    """
    Placeholder for a future AX.25 transmitter implementation.
    """

    def __init__(self, config: AppConfig):
        self.config = config

    def transmit_page(self, page: Page, frame: bytes):
        # TODO: implement AX.25 framing and KISS transmission
        print(f"[AX25] (stub) Would transmit page {page.page_id} ({len(frame)} bytes)")


def build_transmitter(config: AppConfig):
    mode = config.general.mode.lower()
    if mode == "audio":
        return AudioTransmitter(config)
    if mode == "ax25":
        return Ax25Transmitter(config)
    raise ValueError(f"Unknown mode: {config.general.mode}")


