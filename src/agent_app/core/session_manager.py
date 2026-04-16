"""Session manager — capture, restore, and brief the user on startup."""
from __future__ import annotations

import logging
import os
import subprocess
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set

import psutil

try:
    import pygetwindow as gw
except Exception:
    gw = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Apps to never capture / restore (system & background noise)
_IGNORED_EXE_NAMES: Set[str] = {
    "explorer.exe", "searchhost.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "textinputhost.exe",
    "applicationframehost.exe", "systemsettings.exe",
    "lockapp.exe", "runtimebroker.exe", "taskmgr.exe",
    "sentinelai.exe",  # don't restore ourselves
}

# Friendly display names for well-known executables
_FRIENDLY_NAMES: Dict[str, str] = {
    "code.exe": "Visual Studio Code",
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Firefox",
    "notepad++.exe": "Notepad++",
    "devenv.exe": "Visual Studio",
    "idea64.exe": "IntelliJ IDEA",
    "pycharm64.exe": "PyCharm",
    "slack.exe": "Slack",
    "discord.exe": "Discord",
    "spotify.exe": "Spotify",
    "winword.exe": "Microsoft Word",
    "excel.exe": "Microsoft Excel",
    "powerpnt.exe": "Microsoft PowerPoint",
    "outlook.exe": "Microsoft Outlook",
    "windowsterminal.exe": "Windows Terminal",
    "cmd.exe": "Command Prompt",
    "powershell.exe": "PowerShell",
    "pwsh.exe": "PowerShell 7",
    "obs64.exe": "OBS Studio",
    "postman.exe": "Postman",
    "figma.exe": "Figma",
    "notion.exe": "Notion",
}


def capture_open_apps() -> List[Dict[str, Any]]:
    """Capture all user-visible foreground applications.

    Returns a list of dicts with keys: exe_name, exe_path, window_title, friendly_name.
    Deduplicates by exe path so each app appears only once.
    """
    apps: List[Dict[str, Any]] = []
    seen_exe: Set[str] = set()

    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            info = proc.info  # type: ignore[attr-defined]
            exe_name = (info.get("name") or "").lower()
            exe_path = info.get("exe") or ""

            if not exe_path or not exe_name:
                continue
            if exe_name in _IGNORED_EXE_NAMES:
                continue
            if exe_path.lower() in seen_exe:
                continue

            # Only include processes that have a visible window
            if not _has_visible_window(proc.pid):
                continue

            seen_exe.add(exe_path.lower())

            # Get window title for this process
            window_title = _get_window_title_for_pid(proc.pid)
            friendly = _FRIENDLY_NAMES.get(exe_name, exe_name.replace(".exe", "").title())

            apps.append({
                "exe_name": exe_name,
                "exe_path": exe_path,
                "window_title": window_title,
                "friendly_name": friendly,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return apps


def _has_visible_window(pid: int) -> bool:
    """Check if a process has at least one visible window."""
    if gw is None:
        return False
    try:
        for win in gw.getAllWindows():
            if win.title and win.visible:
                # pygetwindow doesn't expose PID directly;
                # fallback: we accept all windowed apps
                return True
    except Exception:
        pass
    # If pygetwindow can't determine, use a heuristic:
    # check if the process has any window handles via ctypes
    try:
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        found = [False]

        def _enum_cb(hwnd: int, _: Any) -> bool:
            if user32.IsWindowVisible(hwnd):
                proc_id = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                if proc_id.value == pid:
                    # Check window has a title (not a background helper)
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        found[0] = True
                        return False  # stop enumerating
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))
        user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
        return found[0]
    except Exception:
        return False


def _get_window_title_for_pid(pid: int) -> str:
    """Get the window title for a given PID using ctypes."""
    try:
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        title = [""]

        def _enum_cb(hwnd: int, _: Any) -> bool:
            if user32.IsWindowVisible(hwnd):
                proc_id = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                if proc_id.value == pid:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title[0] = buf.value
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))
        user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
        return title[0]
    except Exception:
        return ""


def restore_apps(session: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Re-launch apps from a saved session.

    Skips apps that are already running. Returns a list of
    {"app": friendly_name, "status": "launched" | "already_running" | "failed"}.
    """
    results: List[Dict[str, str]] = []
    running_exes = _get_running_exe_names()

    for app in session:
        exe_name = app.get("exe_name", "").lower()
        exe_path = app.get("exe_path", "")
        friendly = app.get("friendly_name", exe_name)

        if exe_name in _IGNORED_EXE_NAMES:
            continue

        if exe_name in running_exes:
            results.append({"app": friendly, "status": "already_running"})
            continue

        if not exe_path or not os.path.isfile(exe_path):
            results.append({"app": friendly, "status": "failed", "reason": "exe not found"})
            continue

        try:
            subprocess.Popen(
                [exe_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            results.append({"app": friendly, "status": "launched"})
            time.sleep(0.5)  # small delay between launches
        except Exception as exc:
            logger.warning("Failed to launch %s: %s", friendly, exc)
            results.append({"app": friendly, "status": "failed", "reason": str(exc)})

    return results


def _get_running_exe_names() -> Set[str]:
    """Get the set of currently running executable names (lowercase)."""
    names: Set[str] = set()
    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info.get("name") or "").lower()  # type: ignore[attr-defined]
            if name:
                names.add(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return names


def build_startup_briefing(briefing_data: Dict[str, Any]) -> str:
    """Build a rich, formatted startup briefing message for the chat window.

    Args:
        briefing_data: dict from Repository.get_startup_briefing()

    Returns:
        A formatted string to display in the chat window.
    """
    today = date.today().strftime("%A, %B %d, %Y")
    now_time = datetime.now().strftime("%I:%M %p")

    lines: List[str] = []
    lines.append(f"🌅 Good {_time_greeting()}! Welcome back.")
    lines.append(f"📅 {today} — {now_time}")
    lines.append("")

    # ── Overview ──
    overview = briefing_data.get("overview", {})
    total = overview.get("total", 0)
    todo = overview.get("todo", 0)
    in_prog = overview.get("in_progress", 0)
    done = overview.get("done", 0)

    lines.append("━━━ 📊 YOUR DASHBOARD ━━━")
    lines.append(f"  📋 Total Tasks: {total}")
    lines.append(f"  🔵 Todo: {todo}  |  🟡 In Progress: {in_prog}  |  ✅ Done: {done}")
    lines.append("")

    # ── In-progress tasks (what you were working on) ──
    in_progress = briefing_data.get("in_progress", [])
    if in_progress:
        lines.append("━━━ 🔨 CONTINUE WHERE YOU LEFT OFF ━━━")
        for t in in_progress[:5]:
            title = t.get("title", "Untitled")
            deadline = t.get("deadline")
            deadline_str = f"  ⏰ Due: {deadline}" if deadline else ""
            lines.append(f"  ▸ {title}{deadline_str}")
        lines.append("")

    # ── Overdue tasks ──
    overdue = briefing_data.get("overdue", [])
    if overdue:
        lines.append("━━━ 🔴 OVERDUE — NEEDS ATTENTION ━━━")
        for t in overdue[:5]:
            title = t.get("title", "Untitled")
            deadline = t.get("deadline", "?")
            lines.append(f"  ⚠️ {title}  (was due: {deadline})")
        lines.append("")

    # ── Upcoming deadlines ──
    upcoming = briefing_data.get("upcoming_deadlines", [])
    # Filter out overdue items already shown
    overdue_ids = {t.get("id") for t in overdue}
    upcoming_only = [t for t in upcoming if t.get("id") not in overdue_ids]
    if upcoming_only:
        lines.append("━━━ ⏰ UPCOMING DEADLINES (7 DAYS) ━━━")
        for t in upcoming_only[:5]:
            title = t.get("title", "Untitled")
            deadline = t.get("deadline", "?")
            status = t.get("status", "todo")
            icon = "🟡" if status == "in_progress" else "🔵"
            lines.append(f"  {icon} {title}  →  Due: {deadline}")
        lines.append("")

    # ── Unread notifications ──
    notifications = briefing_data.get("unread_notifications", [])
    if notifications:
        lines.append("━━━ 🔔 UNREAD NOTIFICATIONS ━━━")
        for n in notifications[:5]:
            msg = n.get("message", "")
            lines.append(f"  • {msg}")
        remaining = len(notifications) - 5
        if remaining > 0:
            lines.append(f"  ... and {remaining} more")
        lines.append("")

    # ── Session restore info ──
    session = briefing_data.get("last_session", [])
    if session:
        app_names = [a.get("friendly_name", "Unknown") for a in session[:8]]
        lines.append("━━━ 🖥️ RESTORING YOUR WORKSPACE ━━━")
        lines.append(f"  Re-opening: {', '.join(app_names)}")
        if len(session) > 8:
            lines.append(f"  ... and {len(session) - 8} more apps")
        lines.append("")

    # ── Quick tips ──
    if not in_progress and not overdue and total == 0:
        lines.append("💡 No tasks yet! Say \"create task Fix the login bug\" to get started.")
    else:
        lines.append("💡 Ask me: \"what should I work on?\" or \"show my deadlines\"")

    return "\n".join(lines)


def _time_greeting() -> str:
    """Return a greeting based on the current hour."""
    hour = datetime.now().hour
    if hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    else:
        return "evening"


def build_voice_briefing(briefing_data: Dict[str, Any]) -> str:
    """Build a natural, spoken version of the startup briefing.

    This is what Sentinel says out loud — conversational, no emojis,
    no formatting. Sounds like a real personal assistant.

    Args:
        briefing_data: dict from Repository.get_startup_briefing()

    Returns:
        A clean text string suitable for text-to-speech.
    """
    greeting = _time_greeting()
    parts: List[str] = []

    parts.append(f"Good {greeting}, sir. Welcome back to Sentinel.")

    # Overview
    overview = briefing_data.get("overview", {})
    total = overview.get("total", 0)
    todo = overview.get("todo", 0)
    in_prog = overview.get("in_progress", 0)
    done = overview.get("done", 0)

    if total > 0:
        parts.append(
            f"You currently have {total} tasks. "
            f"{in_prog} in progress, {todo} to do, and {done} completed."
        )

    # Overdue — mention first since it's urgent
    overdue = briefing_data.get("overdue", [])
    if overdue:
        count = len(overdue)
        first_title = overdue[0].get("title", "a task")
        if count == 1:
            parts.append(
                f"Heads up: you have one overdue task. {first_title} is past its deadline."
            )
        else:
            parts.append(
                f"Attention: you have {count} overdue tasks. "
                f"The most urgent one is {first_title}."
            )

    # In-progress — what to continue
    in_progress = briefing_data.get("in_progress", [])
    if in_progress:
        if len(in_progress) == 1:
            title = in_progress[0].get("title", "your task")
            parts.append(f"You were working on {title}. Shall I continue where you left off?")
        else:
            titles = [t.get("title", "untitled") for t in in_progress[:3]]
            joined = ", ".join(titles[:-1]) + f", and {titles[-1]}" if len(titles) > 1 else titles[0]
            parts.append(
                f"You have {len(in_progress)} tasks in progress: {joined}. "
                f"Which one would you like to focus on?"
            )
    elif todo > 0:
        parts.append(f"You have {todo} tasks waiting. Would you like to pick one to start?")

    # Upcoming deadlines
    upcoming = briefing_data.get("upcoming_deadlines", [])
    overdue_ids = {t.get("id") for t in overdue}
    upcoming_only = [t for t in upcoming if t.get("id") not in overdue_ids]
    if upcoming_only:
        next_task = upcoming_only[0]
        next_title = next_task.get("title", "a task")
        next_deadline = next_task.get("deadline", "soon")
        parts.append(
            f"Your next deadline is {next_title}, due {next_deadline}."
        )
        if len(upcoming_only) > 1:
            parts.append(f"You have {len(upcoming_only)} deadlines coming up this week.")

    # Unread notifications
    notifications = briefing_data.get("unread_notifications", [])
    if notifications:
        parts.append(f"You also have {len(notifications)} unread notifications.")

    # Session restore
    session = briefing_data.get("last_session", [])
    if session:
        app_names = [a.get("friendly_name", "an app") for a in session[:4]]
        joined = ", ".join(app_names[:-1]) + f" and {app_names[-1]}" if len(app_names) > 1 else app_names[0]
        parts.append(f"I'm restoring your workspace. Opening {joined}.")

    # Closing
    if not in_progress and not overdue and total == 0:
        parts.append("No tasks on the board yet. Just say create task, followed by the task name, to get started.")
    else:
        parts.append("I'm listening. Just tell me what you need.")

    return " ".join(parts)
