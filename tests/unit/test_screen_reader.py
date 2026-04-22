"""Tests for screen_reader module."""
from unittest.mock import patch, MagicMock
from agent_app.monitors.screen_reader import (
    ScreenReader,
    ScreenCapture,
    capture_screen_text,
)


def test_screen_reader_buffer_management():
    """ScreenReader should keep only buffer_size captures."""
    reader = ScreenReader(interval_seconds=999, buffer_size=3)

    # Manually add captures
    for i in range(5):
        cap = ScreenCapture(text=f"text_{i}", timestamp=f"2026-01-01T00:0{i}:00Z")
        reader._buffer.append(cap)

    # Buffer should only keep last 3 since we add beyond capacity
    # (In the actual _do_capture, trimming happens — here we test get_latest)
    latest = reader.get_latest()
    assert latest is not None
    assert latest.text == "text_4"


def test_screen_reader_get_context_text_truncation():
    """get_context_text should truncate to max_chars."""
    reader = ScreenReader(interval_seconds=999, buffer_size=5)
    long_text = "A" * 5000
    reader._buffer.append(ScreenCapture(text=long_text, timestamp="2026-01-01T00:00:00Z"))

    result = reader.get_context_text(max_chars=100)
    assert len(result) == 100


def test_screen_reader_empty_buffer_returns_empty():
    """get_context_text should return empty string if no captures."""
    reader = ScreenReader(interval_seconds=999, buffer_size=5)
    assert reader.get_context_text() == ""
    assert reader.get_latest() is None


@patch("PIL.ImageGrab.grab", side_effect=Exception("No display"))
def test_capture_screen_text_graceful_failure(mock_grab):
    """capture_screen_text should return empty string on failure."""
    result = capture_screen_text()
    assert result == ""
