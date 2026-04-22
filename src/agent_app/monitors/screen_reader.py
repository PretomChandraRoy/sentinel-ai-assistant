"""Screen Content Awareness — periodic screenshot + OCR.

Takes screenshots at regular intervals, extracts text using Windows
native OCR (winocr), and keeps a rolling buffer of recent screen
content so the AI brain knows what the user is looking at.

Screenshots are NEVER saved to disk — only extracted text is kept in memory.
"""
from __future__ import annotations
import asyncio
import io
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OCR backend
# ---------------------------------------------------------------------------

def _ocr_extract_text(image_bytes: bytes) -> str:
    """Run Windows native OCR on raw PNG bytes. Returns extracted text."""
    try:
        import winocr  # type: ignore[import-untyped]

        async def _run() -> str:
            result = await winocr.recognize_pil(
                _bytes_to_pil(image_bytes), lang="en"
            )
            return result.text if hasattr(result, "text") else str(result)

        # winocr is async — run in a fresh event loop for this thread
        loop = asyncio.new_event_loop()
        try:
            text = loop.run_until_complete(_run())
        finally:
            loop.close()
        return text.strip()
    except ImportError:
        logger.debug("winocr not available — screen OCR disabled.")
        return ""
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""


def _bytes_to_pil(raw: bytes):  # type: ignore[no-untyped-def]
    from PIL import Image
    return Image.open(io.BytesIO(raw))


def capture_screen_text() -> str:
    """Take a screenshot and return extracted text via OCR."""
    try:
        from PIL import ImageGrab
        screenshot = ImageGrab.grab()
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        raw = buf.getvalue()
        return _ocr_extract_text(raw)
    except Exception as exc:
        logger.warning("Screenshot capture failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Screen reader service
# ---------------------------------------------------------------------------

@dataclass
class ScreenCapture:
    """A single OCR capture result."""
    text: str
    timestamp: str
    active_window: str = ""


@dataclass
class ScreenReader:
    """Periodically captures screen content and keeps a rolling buffer."""

    interval_seconds: int = 60
    buffer_size: int = 5

    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)
    _buffer: Deque[ScreenCapture] = field(default_factory=deque, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def start(self) -> None:
        """Start background screen capture loop."""
        self._thread = threading.Thread(
            target=self._loop, name="screen-reader", daemon=True
        )
        self._thread.start()
        logger.info("ScreenReader started (interval=%ds)", self.interval_seconds)

    def _loop(self) -> None:
        # Do an initial capture right away
        self._do_capture()
        while not self._stop_event.wait(self.interval_seconds):
            self._do_capture()

    def _do_capture(self) -> None:
        try:
            text = capture_screen_text()
            if text:
                capture = ScreenCapture(
                    text=text[:3000],  # Cap at 3000 chars to keep prompt manageable
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                with self._lock:
                    self._buffer.append(capture)
                    while len(self._buffer) > self.buffer_size:
                        self._buffer.popleft()
        except Exception as exc:
            logger.debug("Screen capture cycle failed: %s", exc)

    def get_latest(self) -> Optional[ScreenCapture]:
        """Return the most recent screen capture, or None."""
        with self._lock:
            return self._buffer[-1] if self._buffer else None

    def get_context_text(self, max_chars: int = 2000) -> str:
        """Return the latest screen text, truncated for the AI prompt."""
        latest = self.get_latest()
        if not latest or not latest.text:
            return ""
        text = latest.text[:max_chars]
        return text

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
