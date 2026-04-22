"""Tests for pattern_tracker module."""
import json
from agent_app.core.pattern_tracker import (
    PatternTracker,
    EVENT_APP_FOCUS,
    EVENT_TASK_COMPLETED,
    PATTERN_APP_USAGE,
    PATTERN_PRODUCTIVE_HOURS,
    PATTERN_FOCUS_SCORE,
    _simplify_app_name,
    _parse_event_data,
)


class InMemoryStore:
    """Simple in-memory store to test PatternTracker without a real DB."""

    def __init__(self):
        self.events = []
        self.patterns = {}

    def log(self, event_type, event_data):
        self.events.append({
            "event_type": event_type,
            "event_data": json.dumps(event_data),
        })

    def query(self, hours_back):
        return self.events

    def save_pattern(self, pattern_type, pattern_data):
        self.patterns[pattern_type] = {
            "pattern_type": pattern_type,
            "pattern_data": json.dumps(pattern_data),
        }

    def get_patterns(self, pattern_type, limit=1):
        p = self.patterns.get(pattern_type)
        return [p] if p else []


def _make_tracker():
    store = InMemoryStore()
    tracker = PatternTracker(
        log_fn=store.log,
        query_fn=store.query,
        save_pattern_fn=store.save_pattern,
        get_patterns_fn=store.get_patterns,
    )
    return tracker, store


def test_window_change_logs_events():
    """on_window_change should log app_focus events."""
    tracker, store = _make_tracker()
    tracker._switch_window_start = 1000.0

    tracker.on_window_change("VS Code - main.py")
    tracker.on_window_change("Chrome - Google")

    # First call sets _last_window, second call logs the first window
    assert len(store.events) >= 1
    assert store.events[-1]["event_type"] == EVENT_APP_FOCUS


def test_task_completed_logs_event():
    """on_task_completed should log a task_completed event."""
    tracker, store = _make_tracker()
    tracker.on_task_completed("Fix bug #123", task_id=5)

    assert len(store.events) == 1
    assert store.events[0]["event_type"] == EVENT_TASK_COMPLETED
    data = json.loads(store.events[0]["event_data"])
    assert data["task_id"] == 5


def test_analysis_generates_patterns():
    """_run_analysis should produce app_usage, productive_hours, and focus_score patterns."""
    tracker, store = _make_tracker()

    # Seed some events
    for i in range(10):
        store.events.append({
            "event_type": EVENT_APP_FOCUS,
            "event_data": json.dumps({
                "app": f"main.py - VS Code",
                "duration_seconds": 120,
                "hour": 10,
            }),
        })
    for i in range(3):
        store.events.append({
            "event_type": EVENT_TASK_COMPLETED,
            "event_data": json.dumps({
                "task_title": f"Task {i}",
                "task_id": i,
                "hour": 14,
            }),
        })

    tracker._run_analysis()

    assert PATTERN_APP_USAGE in store.patterns
    assert PATTERN_PRODUCTIVE_HOURS in store.patterns
    assert PATTERN_FOCUS_SCORE in store.patterns


def test_pattern_summary_output():
    """get_pattern_summary should return a readable string."""
    tracker, store = _make_tracker()

    # Seed patterns directly
    store.save_pattern(PATTERN_APP_USAGE, {
        "top_apps": [{"app": "VS Code", "total_seconds": 3600}],
    })
    store.save_pattern(PATTERN_FOCUS_SCORE, {
        "focus_score": 85,
        "switches_per_hour": 7.5,
    })

    summary = tracker.get_pattern_summary()
    assert "VS Code" in summary
    assert "85" in summary


def test_simplify_app_name():
    """_simplify_app_name should extract the app from a window title."""
    assert _simplify_app_name("main.py - VS Code") == "VS Code"
    assert _simplify_app_name("Google - Chrome") == "Chrome"
    assert _simplify_app_name("Notepad") == "Notepad"
    assert _simplify_app_name("") == ""


def test_parse_event_data_handles_strings():
    """_parse_event_data should handle both JSON strings and dicts."""
    assert _parse_event_data({"event_data": '{"key": "val"}'}) == {"key": "val"}
    assert _parse_event_data({"event_data": {"key": "val"}}) == {"key": "val"}
    assert _parse_event_data({}) == {}
