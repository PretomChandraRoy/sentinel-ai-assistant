from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are Sentinel, a voice-first personal AI assistant running locally on the user's PC.
You communicate PRIMARILY through voice (text-to-speech), so keep responses concise and natural-sounding.
You are proactive, helpful, and act like a real personal assistant — tracking work, reminding deadlines,
suggesting next steps, and asking questions when needed.

Current Time: {current_time}

== System Status ==
CPU: {cpu_percent}% | RAM: {ram_percent}% ({ram_used_gb}GB / {ram_total_gb}GB)
Disk Free: {disk_free_gb}GB | Battery: {battery_status}
Active Window: {active_window}

== Tasks Overview ==
Total: {total_tasks} | Todo: {todo_tasks} | In Progress: {in_progress_tasks} | Done: {done_tasks}

== Recent Tasks ==
{recent_tasks}

== Recent Activity ==
{recent_activity}

Guidelines:
- You are a VOICE assistant. Keep responses SHORT (1-3 sentences) unless asked for detail.
- Speak naturally — no markdown, no bullet points, no emojis in responses. Write like you're talking.
- Be proactive: suggest what to work on, remind about deadlines, recommend breaks.
- ASK QUESTIONS to help the user. Examples:
  - "Would you like me to mark that task as done?"
  - "You've been at it for a while. Want me to set a timer for a break?"
  - "Should I create a task for that?"
  - "Which task would you like to focus on first?"
- When the user mentions work, tasks, or deadlines, connect it to their actual task list.
- If the user says something like "create task", "new task", "add task", extract the title and confirm.
- If asked about system status, mention specific numbers from the data above.
- Treat the user respectfully — address them as "sir" occasionally for the assistant feel.
- You can track what they're working on by looking at the active window and recent activity.
"""


@dataclass
class JarvisBrain:
    model: str = "qwen3.5:9b"
    _history: List[Dict[str, str]] = field(default_factory=list, init=False)
    _max_history: int = 20

    def _try_import_ollama(self) -> Any:
        try:
            import ollama as _ollama
            return _ollama
        except ImportError:
            return None

    def build_system_prompt(
        self,
        system_snapshot: Optional[Dict[str, Any]] = None,
        task_overview: Optional[Dict[str, Any]] = None,
        recent_tasks: Optional[List[Dict[str, Any]]] = None,
        recent_activity: Optional[List[Dict[str, Any]]] = None,
        current_time: str = "",
    ) -> str:
        snap = system_snapshot or {}
        overview = task_overview or {"todo": 0, "in_progress": 0, "done": 0, "total": 0}

        battery_pct = snap.get("battery_percent")
        battery_charging = snap.get("battery_charging")
        if battery_pct is not None:
            battery_status = f"{battery_pct}% ({'charging' if battery_charging else 'on battery'})"
        else:
            battery_status = "N/A (desktop)"

        task_lines = ""
        if recent_tasks:
            for t in recent_tasks[:10]:
                task_lines += f"- [{t.get('status', '?')}] {t.get('title', 'Untitled')} (id:{t.get('id', '?')})\n"
        else:
            task_lines = "No tasks found.\n"

        activity_lines = ""
        if recent_activity:
            for a in recent_activity[:10]:
                activity_lines += f"- [{a.get('source', '?')}] {a.get('content', '')}\n"
        else:
            activity_lines = "No recent activity.\n"

        return SYSTEM_PROMPT_TEMPLATE.format(
            current_time=current_time or "unknown",
            cpu_percent=snap.get("cpu_percent", "?"),
            ram_percent=snap.get("ram_percent", "?"),
            ram_used_gb=snap.get("ram_used_gb", "?"),
            ram_total_gb=snap.get("ram_total_gb", "?"),
            disk_free_gb=snap.get("disk_free_gb", "?"),
            battery_status=battery_status,
            active_window=snap.get("active_window", "unknown"),
            total_tasks=overview.get("total", 0),
            todo_tasks=overview.get("todo", 0),
            in_progress_tasks=overview.get("in_progress", 0),
            done_tasks=overview.get("done", 0),
            recent_tasks=task_lines,
            recent_activity=activity_lines,
        )

    def chat(
        self,
        user_message: str,
        system_snapshot: Optional[Dict[str, Any]] = None,
        task_overview: Optional[Dict[str, Any]] = None,
        recent_tasks: Optional[List[Dict[str, Any]]] = None,
        recent_activity: Optional[List[Dict[str, Any]]] = None,
        current_time: str = "",
    ) -> str:
        ollama_mod = self._try_import_ollama()
        if ollama_mod is None:
            return "I can't connect to my AI brain — the `ollama` package is not installed."

        system_prompt = self.build_system_prompt(
            system_snapshot=system_snapshot,
            task_overview=task_overview,
            recent_tasks=recent_tasks,
            recent_activity=recent_activity,
            current_time=current_time,
        )

        self._history.append({"role": "user", "content": user_message})
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        messages = [{"role": "system", "content": system_prompt}] + list(self._history)

        try:
            response = ollama_mod.chat(model=self.model, messages=messages)
            content = response.get("message", {}).get("content", "")
            if not content:
                content = "I received an empty response. Please try again."
        except Exception as exc:
            error_str = str(exc)
            if "connection" in error_str.lower() or "refused" in error_str.lower():
                content = (
                    "I can't reach the Ollama server. Please make sure Ollama is "
                    "running:\n\n1. Install from https://ollama.com\n"
                    "2. Run: `ollama serve`\n"
                    f"3. Pull a model: `ollama pull {self.model}`"
                )
            else:
                content = f"AI error: {error_str}"
                logger.warning("Ollama chat error: %s", error_str)

        self._history.append({"role": "assistant", "content": content})
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        return content

    def summarize_day(
        self,
        task_overview: Optional[Dict[str, Any]] = None,
        recent_tasks: Optional[List[Dict[str, Any]]] = None,
        recent_activity: Optional[List[Dict[str, Any]]] = None,
        current_time: str = "",
    ) -> str:
        prompt = (
            "Give me a concise daily summary of my work today. "
            "Mention what tasks I worked on, what I accomplished, and any notable activity. "
            "Keep it friendly and under 200 words."
        )
        return self.chat(
            user_message=prompt,
            task_overview=task_overview,
            recent_tasks=recent_tasks,
            recent_activity=recent_activity,
            current_time=current_time,
        )

    def clear_history(self) -> None:
        self._history.clear()
