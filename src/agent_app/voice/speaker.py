from __future__ import annotations
import logging
import threading
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VoiceSpeaker:
    """Offline text-to-speech using pyttsx3 (Windows SAPI)."""

    rate: int = 175
    volume: float = 0.9
    _muted: bool = field(default=False, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _speaking: bool = field(default=False, init=False)

    def _create_engine(self):  # type: ignore[no-untyped-def]
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
            voices = engine.getProperty("voices")
            if voices and len(voices) > 1:
                engine.setProperty("voice", voices[1].id)
            return engine
        except Exception:
            return None

    def speak(self, text: str) -> None:
        """Speak text asynchronously (non-blocking)."""
        if self._muted or not text.strip():
            return
        thread = threading.Thread(target=self._speak_sync, args=(text,), daemon=True, name="tts")
        thread.start()

    def speak_and_wait(self, text: str) -> None:
        """Speak text and block until finished. Use for sequential flows."""
        if self._muted or not text.strip():
            return
        self._speak_sync(text)

    def _speak_sync(self, text: str) -> None:
        with self._lock:
            self._speaking = True
            engine = self._create_engine()
            if engine is None:
                self._speaking = False
                return
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass
            finally:
                self._speaking = False
                try:
                    engine.stop()
                except Exception:
                    pass

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    @property
    def muted(self) -> bool:
        return self._muted

    def toggle_mute(self) -> bool:
        self._muted = not self._muted
        return self._muted

    def set_mute(self, muted: bool) -> None:
        self._muted = muted
