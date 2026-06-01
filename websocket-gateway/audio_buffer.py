import base64
from dataclasses import dataclass
from typing import Optional


@dataclass
class BufferedWindow:
    audio_base64: str
    seq: int
    is_final: bool


class AudioBuffer:
    def __init__(self, chunk_window_size: int = 3) -> None:
        self._chunk_window_size = chunk_window_size
        self._latest_audio_base64: Optional[str] = None
        self._chunk_count = 0
        self._last_seq = 0

    def reset(self) -> None:
        self._latest_audio_base64 = None
        self._chunk_count = 0
        self._last_seq = 0

    def add_chunk(self, data: str, seq: int, is_final: bool) -> Optional[BufferedWindow]:
        self._last_seq = seq
        if data:
            self._chunk_count += 1
            self._latest_audio_base64 = data

            payload = data.split(",", 1)[1] if "," in data else data
            base64.b64decode(payload or "", validate=False)

        if is_final:
            audio_base64 = data or self._latest_audio_base64 or ""
            window = BufferedWindow(audio_base64=audio_base64, seq=seq, is_final=True)
            self.reset()
            return window

        return None

    def force_finalize(self) -> Optional[BufferedWindow]:
        if not self._latest_audio_base64:
            return None
        window = BufferedWindow(audio_base64=self._latest_audio_base64, seq=self._last_seq, is_final=True)
        self.reset()
        return window

    @property
    def last_seq(self) -> int:
        return self._last_seq
