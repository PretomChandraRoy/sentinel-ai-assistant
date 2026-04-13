from __future__ import annotations
import threading
from dataclasses import dataclass, field
from typing import Optional

import pystray


AlertCallback = None  # type alias placeholder


@dataclass
class Notifier:
    """Sends Windows toast/balloon notifications via the system tray icon."""

    _icon: Optional[pystray.Icon] = field(default=None, init=False, repr=False)

    def set_icon(self, icon: pystray.Icon) -> None:
        self._icon = icon

    def notify(self, title: str, message: str) -> None:
        if self._icon is not None:
            try:
                self._icon.notify(message, title=title)
            except Exception:
                pass

    def alert_handler(self, alert_type: str, message: str) -> None:
        title_map = {
            "battery_low": "🔋 Battery Low",
            "high_cpu": "🔥 High CPU",
            "high_ram": "💾 High RAM",
            "task_stuck": "📌 Task Stuck",
        }
        title = title_map.get(alert_type, "JARVIS Alert")
        self.notify(title, message)
