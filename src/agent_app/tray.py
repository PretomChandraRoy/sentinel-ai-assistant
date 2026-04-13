from __future__ import annotations
import io
import logging
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from agent_app.config import AppSettings
from agent_app.core.brain import JarvisBrain
from agent_app.core.orchestrator import SyncOrchestrator
from agent_app.core.retry_queue import RetryQueueService
from agent_app.core.sync import SyncService
from agent_app.db.repository import Repository
from agent_app.integrations.git import GitAdapter
from agent_app.integrations.github_issues import GitHubIssuesAdapter
from agent_app.integrations.jira import JiraAdapter
from agent_app.integrations.workfiles import WorkfilesAdapter
from agent_app.monitors.notifier import Notifier
from agent_app.monitors.system_monitor import (
    SystemMonitor,
    capture_snapshot,
    snapshot_to_dict,
)
from agent_app.voice.listener import VoiceListener
from agent_app.voice.speaker import VoiceSpeaker

logger = logging.getLogger(__name__)


def _create_tray_icon_image():  # type: ignore[no-untyped-def]
    """Create a simple 64x64 tray icon with a 'J' letter."""
    from PIL import Image, ImageDraw, ImageFont
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size - 2, size - 2], fill=(15, 52, 96), outline=(0, 210, 255), width=2)
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    draw.text((size // 2, size // 2), "J", fill=(0, 210, 255), font=font, anchor="mm")
    return img


class JarvisApp:
    """Main application tying together tray, chat, brain, monitors, and voice.

    PyQt6 runs on the MAIN thread (required).
    pystray runs in a BACKGROUND thread.
    """

    def __init__(self, settings: Optional[AppSettings] = None) -> None:
        self.settings = settings or AppSettings.from_env()
        self.repo = Repository(self.settings.db_path)
        self.repo.init_schema()

        # Integrations & sync
        adapters = {
            "jira": JiraAdapter(issue_key_resolver=self.repo.get_jira_issue_key),
            "github": GitHubIssuesAdapter(),
            "git": GitAdapter(workspace_root=self.settings.workspace_root),
            "workfiles": WorkfilesAdapter(
                workspace_root=self.settings.workspace_root, extra_folders=[]
            ),
        }
        sync_service = SyncService(repo=self.repo, adapters=adapters)
        retry_service = RetryQueueService(repo=self.repo, adapters=adapters)
        self.orchestrator = SyncOrchestrator(
            sync_service=sync_service,
            retry_service=retry_service,
            interval_seconds=self.settings.polling_interval_seconds,
        )

        # AI brain
        self.brain = JarvisBrain()

        # Notifier
        self.notifier = Notifier()

        # System monitor
        self.system_monitor = SystemMonitor(
            interval_seconds=30,
            on_alert=self._on_system_alert,
        )

        # Voice
        self.speaker = VoiceSpeaker()
        self.listener = VoiceListener(on_speech=self._on_speech)
        self._voice_enabled = True

        # Chat window (created later on main thread)
        self._window = None  # type: ignore[assignment]
        self._tray_icon = None  # type: ignore[assignment]

        # Status update thread
        self._status_stop = threading.Event()

    def run(self) -> None:
        """Start all services and run PyQt6 on the main thread."""
        logger.info("Starting JARVIS...")

        # Start background services
        self.orchestrator.start()
        self.system_monitor.start()

        # Start tray icon in background thread
        tray_thread = threading.Thread(target=self._run_tray, daemon=True, name="tray-icon")
        tray_thread.start()

        # Start status bar updates in background
        status_thread = threading.Thread(target=self._status_loop, daemon=True, name="status-update")
        status_thread.start()

        # Run PyQt6 on the MAIN thread (this is required by Qt)
        self._run_qt_main()

        # Cleanup when Qt exits
        self._cleanup()

    def _run_qt_main(self) -> None:
        """Create QApplication and main window on the main thread."""
        from PyQt6.QtWidgets import QApplication
        from agent_app.gui.chat_window import JarvisMainWindow

        app = QApplication.instance() or QApplication(sys.argv)
        self._window = JarvisMainWindow(
            on_send=self._on_chat_send,
            on_mic_click=self._on_mic_click,
        )
        self._window.setWindowTitle("J.A.R.V.I.S.")
        self._window.show()

        app.exec()

    def _run_tray(self) -> None:
        """Run pystray in a background thread."""
        import pystray

        icon_image = _create_tray_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Open JARVIS", self._show_chat, default=True),
            pystray.MenuItem("Sync Now", self._trigger_sync),
            pystray.MenuItem(
                "Voice",
                pystray.Menu(
                    pystray.MenuItem(
                        lambda item: "🔇 Mute Voice" if not self.speaker.muted else "🔊 Unmute Voice",
                        self._toggle_voice,
                    ),
                ),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

        icon = pystray.Icon("jarvis", icon_image, "JARVIS - AI Assistant", menu)
        self._tray_icon = icon
        self.notifier.set_icon(icon)
        icon.run()

    def _cleanup(self) -> None:
        self._status_stop.set()
        self.system_monitor.stop()
        self.orchestrator.stop()
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass

    # ---- Tray menu handlers ----

    def _show_chat(self, icon: Any = None, item: Any = None) -> None:
        if self._window:
            try:
                from PyQt6.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(self._window, "show", Qt.ConnectionType.QueuedConnection)
                QMetaObject.invokeMethod(self._window, "raise_", Qt.ConnectionType.QueuedConnection)
            except Exception:
                pass

    def _trigger_sync(self, icon: Any = None, item: Any = None) -> None:
        if self._window:
            self._window.add_message("system", "Syncing all sources...")
        result = self.orchestrator.trigger_sync()
        total = sum(result.values())
        if self._window:
            self._window.add_message("system", f"Sync complete: {total} events from {len(result)} sources.")

    def _toggle_voice(self, icon: Any = None, item: Any = None) -> None:
        muted = self.speaker.toggle_mute()
        state = "muted" if muted else "unmuted"
        if self._window:
            self._window.add_message("system", f"Voice {state}.")

    def _quit(self, icon: Any = None, item: Any = None) -> None:
        self.repo.create_daily_snapshot()
        if self._window:
            try:
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    app.quit()
            except Exception:
                pass
        if icon:
            icon.stop()

    # ---- Chat handlers ----

    def _on_chat_send(self, message: str) -> None:
        self.repo.save_chat_message("user", message)

        # Build context
        snap = self.system_monitor.get_latest()
        snap_dict = snapshot_to_dict(snap) if snap else {}
        overview = self.repo.dashboard_overview()
        tasks = self.repo.list_tasks()[:10]
        activity = self.repo.recent_progress(limit=10)
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Get AI response
        response = self.brain.chat(
            user_message=message,
            system_snapshot=snap_dict,
            task_overview=overview,
            recent_tasks=tasks,
            recent_activity=activity,
            current_time=current_time,
        )

        self.repo.save_chat_message("assistant", response)
        if self._window:
            self._window.add_message("assistant", response)

        # Speak response if voice is enabled
        if self._voice_enabled and not self.speaker.muted:
            self.speaker.speak(response)

    def _on_mic_click(self) -> None:
        if self.listener.is_listening:
            return
        if self._window:
            self._window.set_mic_listening(True)
            self._window.add_message("system", "Listening...")
        self.listener.listen_async()

    def _on_speech(self, text: str) -> None:
        if self._window:
            self._window.set_mic_listening(False)
            self._window.set_entry_text(text)
            self._window.add_message("system", f"Heard: \"{text}\"")
        self._on_chat_send(text)

    # ---- System alerts ----

    def _on_system_alert(self, alert_type: str, message: str) -> None:
        self.repo.add_notification(alert_type, message)
        self.notifier.alert_handler(alert_type, message)
        if self._window:
            self._window.add_message("system", f"⚠️ {message}")

    # ---- Status bar loop ----

    def _status_loop(self) -> None:
        while not self._status_stop.wait(5):
            snap = self.system_monitor.get_latest()
            if snap and self._window:
                self._window.update_status(
                    cpu=snap.cpu_percent,
                    ram=snap.ram_percent,
                    battery=snap.battery_percent,
                )


def launch_jarvis(settings: Optional[AppSettings] = None) -> None:
    """Entry point to launch JARVIS."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    app = JarvisApp(settings=settings)
    app.run()
