"""User Pattern Learning — tracks behavioral patterns over time.

Logs events (app focus, task completions, session durations) into the
database and periodically aggregates them into human-readable pattern
insights that feed into the AI brain's system prompt.
"""
from __future__ import annotations
import json
import logging
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

EVENT_APP_FOCUS = "app_focus"
EVENT_TASK_COMPLETED = "task_completed"
EVENT_SESSION_START = "session_start"
EVENT_SESSION_END = "session_end"
EVENT_APP_SWITCH = "app_switch"

PATTERN_APP_USAGE = "app_usage"
PATTERN_PRODUCTIVE_HOURS = "productive_hours"
PATTERN_SESSION_DURATION = "session_duration"
PATTERN_FOCUS_SCORE = "focus_score"


# ---------------------------------------------------------------------------
# Pattern Tracker
# ---------------------------------------------------------------------------

@dataclass
class PatternTracker:
    """Tracks user behavior and generates pattern insights.

    Requires:
    - log_fn:  callable(event_type, event_data_dict) to persist events
    - query_fn: callable(hours_back) -> list of event dicts from DB
    - save_pattern_fn: callable(pattern_type, pattern_data_dict) to persist insights
    - get_patterns_fn: callable(pattern_type, limit) -> list of pattern dicts
    """

    log_fn: Callable[[str, Dict[str, Any]], None]
    query_fn: Callable[[int], List[Dict[str, Any]]]
    save_pattern_fn: Callable[[str, Dict[str, Any]], None]
    get_patterns_fn: Callable[[str, int], List[Dict[str, Any]]]

    analysis_interval: int = 600  # 10 minutes

    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)
    _last_window: str = field(default="", init=False)
    _session_start: str = field(default="", init=False)
    _switch_count: int = field(default=0, init=False)
    _switch_window_start: float = field(default=0.0, init=False)

    def start(self) -> None:
        self._session_start = datetime.now(timezone.utc).isoformat()
        self.log_fn(EVENT_SESSION_START, {"timestamp": self._session_start})
        self._switch_window_start = time.time()

        self._thread = threading.Thread(
            target=self._analysis_loop, name="pattern-tracker", daemon=True
        )
        self._thread.start()
        logger.info("PatternTracker started (analysis every %ds)", self.analysis_interval)

    def on_window_change(self, window_title: str) -> None:
        """Call whenever the active window changes."""
        if not window_title or window_title == self._last_window:
            return

        now = time.time()
        duration = now - self._switch_window_start if self._switch_window_start else 0

        if self._last_window:
            self._switch_count += 1
            self.log_fn(EVENT_APP_FOCUS, {
                "app": self._last_window,
                "duration_seconds": round(duration),
                "hour": datetime.now().hour,
            })

        self._last_window = window_title
        self._switch_window_start = now

    def on_task_completed(self, task_title: str, task_id: int) -> None:
        """Call when a task is marked as done."""
        self.log_fn(EVENT_TASK_COMPLETED, {
            "task_title": task_title,
            "task_id": task_id,
            "hour": datetime.now().hour,
        })

    def stop(self) -> None:
        # Log session end
        self.log_fn(EVENT_SESSION_END, {
            "session_start": self._session_start,
            "session_end": datetime.now(timezone.utc).isoformat(),
        })
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    # ---- Analysis loop ----

    def _analysis_loop(self) -> None:
        while not self._stop_event.wait(self.analysis_interval):
            try:
                self._run_analysis()
            except Exception as exc:
                logger.warning("Pattern analysis failed: %s", exc)

    def _run_analysis(self) -> None:
        """Aggregate recent events into pattern insights."""
        # Analyze last 24 hours of data
        events = self.query_fn(24)
        if not events:
            return

        self._analyze_app_usage(events)
        self._analyze_productive_hours(events)
        self._analyze_focus_score(events)

    def _analyze_app_usage(self, events: List[Dict[str, Any]]) -> None:
        """Which apps are used most, and at what times."""
        app_counter: Counter = Counter()
        app_hours: Dict[str, Counter] = defaultdict(Counter)

        for ev in events:
            if ev.get("event_type") != EVENT_APP_FOCUS:
                continue
            data = _parse_event_data(ev)
            app = _simplify_app_name(data.get("app", ""))
            if not app:
                continue
            duration = data.get("duration_seconds", 0)
            hour = data.get("hour", 0)
            app_counter[app] += duration
            app_hours[app][hour] += duration

        if not app_counter:
            return

        top_apps = app_counter.most_common(5)
        pattern_data = {
            "top_apps": [{"app": app, "total_seconds": secs} for app, secs in top_apps],
            "app_hours": {
                app: dict(hours.most_common(3))
                for app, hours in list(app_hours.items())[:5]
            },
        }
        self.save_pattern_fn(PATTERN_APP_USAGE, pattern_data)

    def _analyze_productive_hours(self, events: List[Dict[str, Any]]) -> None:
        """Which hours have the most task completions."""
        hour_completions: Counter = Counter()
        for ev in events:
            if ev.get("event_type") != EVENT_TASK_COMPLETED:
                continue
            data = _parse_event_data(ev)
            hour = data.get("hour", 0)
            hour_completions[hour] += 1

        if not hour_completions:
            return

        peak_hours = hour_completions.most_common(3)
        self.save_pattern_fn(PATTERN_PRODUCTIVE_HOURS, {
            "peak_hours": [{"hour": h, "completions": c} for h, c in peak_hours],
            "total_completions_24h": sum(hour_completions.values()),
        })

    def _analyze_focus_score(self, events: List[Dict[str, Any]]) -> None:
        """Calculate a focus score based on app-switch frequency."""
        switches = sum(
            1 for ev in events
            if ev.get("event_type") == EVENT_APP_FOCUS
        )
        total_hours = max(1, len(set(
            _parse_event_data(ev).get("hour", 0)
            for ev in events
            if ev.get("event_type") == EVENT_APP_FOCUS
        )))

        switches_per_hour = switches / total_hours
        # Score: fewer switches = higher focus (0-100)
        focus_score = max(0, min(100, int(100 - switches_per_hour * 2)))

        self.save_pattern_fn(PATTERN_FOCUS_SCORE, {
            "focus_score": focus_score,
            "switches_per_hour": round(switches_per_hour, 1),
            "total_switches": switches,
        })

    # ---- Build context for AI ----

    def get_pattern_summary(self) -> str:
        """Build a human-readable pattern summary for the AI prompt."""
        lines = []

        # App usage
        app_patterns = self.get_patterns_fn(PATTERN_APP_USAGE, 1)
        if app_patterns:
            data = _parse_event_data(app_patterns[0])
            top_apps = data.get("top_apps", [])
            if top_apps:
                apps_str = ", ".join(
                    f"{a['app']} ({a['total_seconds'] // 60}min)"
                    for a in top_apps[:3]
                )
                lines.append(f"Most used apps (24h): {apps_str}")

        # Productive hours
        prod_patterns = self.get_patterns_fn(PATTERN_PRODUCTIVE_HOURS, 1)
        if prod_patterns:
            data = _parse_event_data(prod_patterns[0])
            peak = data.get("peak_hours", [])
            if peak:
                hours_str = ", ".join(f"{h['hour']}:00" for h in peak)
                lines.append(f"Peak productive hours: {hours_str}")
            total = data.get("total_completions_24h", 0)
            if total:
                lines.append(f"Tasks completed in last 24h: {total}")

        # Focus score
        focus_patterns = self.get_patterns_fn(PATTERN_FOCUS_SCORE, 1)
        if focus_patterns:
            data = _parse_event_data(focus_patterns[0])
            score = data.get("focus_score", 0)
            sph = data.get("switches_per_hour", 0)
            lines.append(f"Focus score: {score}/100 ({sph} app switches/hour)")

        # Session duration
        if self._session_start:
            try:
                start = datetime.fromisoformat(self._session_start)
                duration = datetime.now(timezone.utc) - start
                mins = int(duration.total_seconds() // 60)
                lines.append(f"Current session: {mins} minutes")
            except Exception:
                pass

        return "\n".join(lines) if lines else "No patterns recorded yet."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_event_data(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Parse event_data / pattern_data which may be a JSON string or dict."""
    raw = ev.get("event_data") or ev.get("pattern_data") or "{}"
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return raw if isinstance(raw, dict) else {}


def _simplify_app_name(title: str) -> str:
    """Extract a short app name from a window title."""
    if not title:
        return ""
    # Common patterns: "filename - App Name", "App Name - detail"
    parts = title.split(" - ")
    if len(parts) >= 2:
        # Last segment is usually the app name
        return parts[-1].strip()[:40]
    return title.strip()[:40]
