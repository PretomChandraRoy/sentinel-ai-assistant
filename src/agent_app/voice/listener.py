from __future__ import annotations
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)

SpeechCallback = Callable[[str], None]


@dataclass
class VoiceListener:
    """Voice listener with both push-to-talk and continuous listening modes.

    Push-to-talk: call listen_async() to capture a single phrase.
    Continuous:   call start_continuous() to keep listening until stopped.
    """

    on_speech: Optional[SpeechCallback] = None
    language: str = "en-US"
    _listening: bool = field(default=False, init=False)
    _continuous: bool = field(default=False, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)

    def _try_import(self):  # type: ignore[no-untyped-def]
        try:
            import speech_recognition as sr
            return sr
        except ImportError:
            return None

    def listen_once(self) -> Optional[str]:
        """Capture a single phrase from the microphone."""
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
        """Push-to-talk: capture one phrase, then stop."""
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

    # ── Continuous listening mode ──

    def start_continuous(self) -> None:
        """Start continuous listening — keeps capturing speech in a loop.

        Each recognized phrase is sent to on_speech callback.
        Call stop_continuous() to stop.
        """
        if self._continuous:
            return
        self._continuous = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._continuous_loop, daemon=True, name="voice-continuous"
        )
        self._thread.start()
        logger.info("Continuous voice listening started.")

    def stop_continuous(self) -> None:
        """Stop continuous listening mode."""
        if not self._continuous:
            return
        self._continuous = False
        self._stop_event.set()
        logger.info("Continuous voice listening stopped.")

    def _continuous_loop(self) -> None:
        """Background loop: listen → recognize → callback → repeat."""
        sr = self._try_import()
        if sr is None:
            logger.warning("speech_recognition not available, continuous mode disabled.")
            self._continuous = False
            return

        recognizer = sr.Recognizer()
        # Reduce pause threshold for snappier responses
        recognizer.pause_threshold = 1.0
        recognizer.dynamic_energy_threshold = True

        while not self._stop_event.is_set():
            try:
                with sr.Microphone() as source:
                    if self._stop_event.is_set():
                        break
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    self._listening = True
                    audio = recognizer.listen(
                        source, timeout=10, phrase_time_limit=20
                    )
                    self._listening = False
            except Exception:
                self._listening = False
                # Timeout or mic error, just retry
                if self._stop_event.is_set():
                    break
                continue

            if self._stop_event.is_set():
                break

            # Recognize in the same thread to keep sequential
            try:
                text = recognizer.recognize_google(audio, language=self.language)
                text = str(text).strip()
                if text and self.on_speech:
                    self.on_speech(text)
            except Exception:
                # Unrecognized audio, silently continue
                pass

        self._listening = False
        self._continuous = False

    @property
    def is_listening(self) -> bool:
        return self._listening

    @property
    def is_continuous(self) -> bool:
        return self._continuous
