from __future__ import annotations
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

SpeechCallback = Callable[[str], None]


@dataclass
class VoiceListener:
    """Push-to-talk voice listener using Google free speech API."""

    on_speech: Optional[SpeechCallback] = None
    language: str = "en-US"
    _listening: bool = field(default=False, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)

    def _try_import(self):  # type: ignore[no-untyped-def]
        try:
            import speech_recognition as sr
            return sr
        except ImportError:
            return None

    def listen_once(self) -> Optional[str]:
        sr = self._try_import()
        if sr is None:
            return None
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)
            text = recognizer.recognize_google(audio, language=self.language)
            return str(text)
        except Exception:
            return None

    def listen_async(self) -> None:
        if self._listening:
            return
        self._listening = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="voice-listen")
        self._thread.start()

    def _listen_loop(self) -> None:
        result = self.listen_once()
        self._listening = False
        if result and self.on_speech:
            self.on_speech(result)

    @property
    def is_listening(self) -> bool:
        return self._listening
