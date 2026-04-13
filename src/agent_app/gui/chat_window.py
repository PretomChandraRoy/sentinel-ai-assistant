from __future__ import annotations
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QFont, QColor, QIcon, QPixmap, QPainter, QLinearGradient, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QFrame, QScrollArea,
    QSizePolicy, QGraphicsDropShadowEffect,
)


# ── Color palette ──
COLORS = {
    "bg_darkest": "#0a0e17",
    "bg_dark": "#0f1724",
    "bg_medium": "#162032",
    "bg_card": "#1a2438",
    "accent_blue": "#00d4ff",
    "accent_purple": "#7c3aed",
    "accent_gradient_start": "#6366f1",
    "accent_gradient_end": "#06b6d4",
    "text_primary": "#e2e8f0",
    "text_secondary": "#94a3b8",
    "text_dim": "#475569",
    "user_bubble": "#1e293b",
    "ai_bubble": "#0f172a",
    "success": "#10b981",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "border": "#1e293b",
}

STYLESHEET = f"""
QMainWindow {{
    background-color: {COLORS["bg_darkest"]};
}}
QWidget#centralWidget {{
    background-color: {COLORS["bg_darkest"]};
}}
QTextEdit#chatDisplay {{
    background-color: {COLORS["bg_dark"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 16px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
    selection-background-color: {COLORS["accent_purple"]};
}}
QLineEdit#messageInput {{
    background-color: {COLORS["bg_medium"]};
    color: {COLORS["text_primary"]};
    border: 2px solid {COLORS["border"]};
    border-radius: 24px;
    padding: 12px 20px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
    selection-background-color: {COLORS["accent_purple"]};
}}
QLineEdit#messageInput:focus {{
    border-color: {COLORS["accent_blue"]};
}}
QPushButton#sendButton {{
    background-color: {COLORS["accent_purple"]};
    color: white;
    border: none;
    border-radius: 24px;
    padding: 12px 24px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
    font-weight: bold;
    min-width: 80px;
}}
QPushButton#sendButton:hover {{
    background-color: #8b5cf6;
}}
QPushButton#sendButton:pressed {{
    background-color: #6d28d9;
}}
QPushButton#micButton {{
    background-color: {COLORS["bg_medium"]};
    color: {COLORS["accent_blue"]};
    border: 2px solid {COLORS["border"]};
    border-radius: 24px;
    padding: 10px;
    font-size: 18px;
    min-width: 48px;
    max-width: 48px;
    min-height: 48px;
    max-height: 48px;
}}
QPushButton#micButton:hover {{
    border-color: {COLORS["accent_blue"]};
    background-color: {COLORS["bg_card"]};
}}
QLabel#statusBar {{
    background-color: {COLORS["bg_medium"]};
    color: {COLORS["text_secondary"]};
    border-radius: 8px;
    padding: 6px 14px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
}}
QFrame#headerFrame {{
    background-color: {COLORS["bg_dark"]};
    border-bottom: 1px solid {COLORS["border"]};
}}
"""


class _Signals(QObject):
    """Thread-safe signal bridge for updating the GUI from worker threads."""
    add_message = pyqtSignal(str, str)       # role, content
    update_status = pyqtSignal(float, float, object)  # cpu, ram, battery
    set_mic_listening = pyqtSignal(bool)
    set_entry_text = pyqtSignal(str)


class JarvisMainWindow(QMainWindow):
    def __init__(
        self,
        on_send: Optional[Callable[[str], None]] = None,
        on_mic_click: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__()
        self._on_send = on_send
        self._on_mic_click = on_mic_click
        self.signals = _Signals()

        self.setWindowTitle("J.A.R.V.I.S.")
        self.setMinimumSize(560, 720)
        self.resize(560, 720)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = self._build_header()
        layout.addWidget(header)

        # Chat area
        self._chat_display = QTextEdit()
        self._chat_display.setObjectName("chatDisplay")
        self._chat_display.setReadOnly(True)
        layout.addWidget(self._chat_display, stretch=1)

        # Status bar
        self._status_label = QLabel("  ⏳ Initializing system monitor...")
        self._status_label.setObjectName("statusBar")
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(12, 4, 12, 4)
        status_layout.addWidget(self._status_label)
        layout.addWidget(status_container)

        # Input area
        input_widget = self._build_input()
        layout.addWidget(input_widget)

        # Connect signals
        self.signals.add_message.connect(self._do_add_message)
        self.signals.update_status.connect(self._do_update_status)
        self.signals.set_mic_listening.connect(self._do_set_mic_listening)
        self.signals.set_entry_text.connect(self._do_set_entry_text)

        # Welcome
        self._do_add_message("assistant",
            "Hello! I'm JARVIS, your personal AI assistant.\n"
            "Type a message or click 🎤 to speak. How can I help?"
        )

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("headerFrame")
        frame.setFixedHeight(64)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 0, 20, 0)

        # Glowing dot
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {COLORS['accent_blue']}; font-size: 14px;")
        layout.addWidget(dot)

        title = QLabel("J.A.R.V.I.S.")
        title.setStyleSheet(
            f"color: {COLORS['accent_blue']}; font-size: 20px; font-weight: bold; "
            f"font-family: 'Consolas', monospace; letter-spacing: 3px;"
        )
        layout.addWidget(title)

        subtitle = QLabel("Just A Rather Very Intelligent System")
        subtitle.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; font-family: 'Segoe UI';"
        )
        layout.addWidget(subtitle)
        layout.addStretch()

        online_badge = QLabel("● ONLINE")
        online_badge.setStyleSheet(
            f"color: {COLORS['success']}; font-size: 10px; font-weight: bold; "
            f"font-family: 'Consolas';"
        )
        layout.addWidget(online_badge)

        return frame

    def _build_input(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet(f"background-color: {COLORS['bg_darkest']};")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        # Mic button
        self._mic_button = QPushButton("🎤")
        self._mic_button.setObjectName("micButton")
        self._mic_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mic_button.clicked.connect(self._handle_mic)
        layout.addWidget(self._mic_button)

        # Text input
        self._entry = QLineEdit()
        self._entry.setObjectName("messageInput")
        self._entry.setPlaceholderText("Type a message to JARVIS...")
        self._entry.returnPressed.connect(self._handle_send)
        layout.addWidget(self._entry, stretch=1)

        # Send button
        send_btn = QPushButton("Send ➤")
        send_btn.setObjectName("sendButton")
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.clicked.connect(self._handle_send)
        layout.addWidget(send_btn)

        return container

    # ── User interaction handlers ──

    def _handle_send(self) -> None:
        text = self._entry.text().strip()
        if not text:
            return
        self._entry.clear()
        self._do_add_message("user", text)
        if self._on_send:
            threading.Thread(target=self._on_send, args=(text,), daemon=True).start()

    def _handle_mic(self) -> None:
        if self._on_mic_click:
            self._on_mic_click()

    # ── Slots (called via signals from any thread) ──

    def _do_add_message(self, role: str, content: str) -> None:
        timestamp = datetime.now().strftime("%H:%M")
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if role == "user":
            html = (
                f'<div style="margin: 8px 0; padding: 10px 16px; '
                f'background-color: {COLORS["user_bubble"]}; border-radius: 12px; '
                f'border-left: 3px solid {COLORS["accent_blue"]};">'
                f'<span style="color: {COLORS["accent_blue"]}; font-weight: bold; '
                f'font-size: 11px;">You</span>'
                f'<span style="color: {COLORS["text_dim"]}; font-size: 9px;"> {timestamp}</span>'
                f'<br/><span style="color: {COLORS["text_primary"]}; font-size: 13px;">'
                f'{_escape_html(content)}</span></div>'
            )
        elif role == "system":
            html = (
                f'<div style="margin: 4px 0; padding: 6px 14px; text-align: center;">'
                f'<span style="color: {COLORS["warning"]}; font-size: 11px; font-style: italic;">'
                f'⚡ {_escape_html(content)}</span></div>'
            )
        else:
            html = (
                f'<div style="margin: 8px 0; padding: 10px 16px; '
                f'background-color: {COLORS["ai_bubble"]}; border-radius: 12px; '
                f'border-left: 3px solid {COLORS["accent_purple"]};">'
                f'<span style="color: #a78bfa; font-weight: bold; '
                f'font-size: 11px;">JARVIS</span>'
                f'<span style="color: {COLORS["text_dim"]}; font-size: 9px;"> {timestamp}</span>'
                f'<br/><span style="color: {COLORS["text_secondary"]}; font-size: 13px;">'
                f'{_escape_html(content)}</span></div>'
            )

        cursor.insertHtml(html)
        cursor.insertText("\n")
        self._chat_display.setTextCursor(cursor)
        self._chat_display.ensureCursorVisible()

    def _do_update_status(self, cpu: float, ram: float, battery: object) -> None:
        bat_str = f"{battery:.0f}%" if battery is not None else "N/A"
        cpu_icon = "🟢" if cpu < 70 else "🟡" if cpu < 90 else "🔴"
        ram_icon = "🟢" if ram < 70 else "🟡" if ram < 90 else "🔴"
        self._status_label.setText(
            f"  {cpu_icon} CPU {cpu:.0f}%  │  {ram_icon} RAM {ram:.0f}%  │  🔋 {bat_str}"
        )

    def _do_set_mic_listening(self, listening: bool) -> None:
        if listening:
            self._mic_button.setText("🔴")
            self._mic_button.setStyleSheet(
                f"background-color: {COLORS['danger']}; color: white; "
                f"border: 2px solid {COLORS['danger']}; border-radius: 24px; "
                f"font-size: 18px; min-width: 48px; max-width: 48px; "
                f"min-height: 48px; max-height: 48px;"
            )
        else:
            self._mic_button.setText("🎤")
            self._mic_button.setStyleSheet("")  # revert to stylesheet default

    def _do_set_entry_text(self, text: str) -> None:
        self._entry.setText(text)

    # ── Public API (thread-safe) ──

    def add_message(self, role: str, content: str) -> None:
        self.signals.add_message.emit(role, content)

    def update_status(self, cpu: float, ram: float, battery: Optional[float] = None) -> None:
        self.signals.update_status.emit(cpu, ram, battery)

    def set_mic_listening(self, listening: bool) -> None:
        self.signals.set_mic_listening.emit(listening)

    def set_entry_text(self, text: str) -> None:
        self.signals.set_entry_text.emit(text)

    def closeEvent(self, event: Any) -> None:
        self.hide()
        event.ignore()


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


@dataclass
class ChatWindow:
    """Wrapper that manages the QApplication + JarvisMainWindow lifecycle."""

    on_send: Optional[Callable[[str], None]] = None
    on_mic_click: Optional[Callable[[], None]] = None
    title: str = "J.A.R.V.I.S."

    _app: Optional[QApplication] = field(default=None, init=False, repr=False)
    _window: Optional[JarvisMainWindow] = field(default=None, init=False, repr=False)
    _ready_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="chat-gui")
        self._thread.start()
        self._ready_event.wait(timeout=15)

    def _run(self) -> None:
        self._app = QApplication.instance() or QApplication(sys.argv)  # type: ignore[assignment]
        self._window = JarvisMainWindow(
            on_send=self.on_send,
            on_mic_click=self.on_mic_click,
        )
        self._window.setWindowTitle(self.title)
        self._window.show()
        self._ready_event.set()
        self._app.exec()

    # ── Delegate to window (thread-safe via signals) ──

    def add_message(self, role: str, content: str) -> None:
        if self._window:
            self._window.add_message(role, content)

    def update_status(self, cpu: float, ram: float, battery: Optional[float] = None) -> None:
        if self._window:
            self._window.update_status(cpu, ram, battery)

    def set_mic_listening(self, listening: bool) -> None:
        if self._window:
            self._window.set_mic_listening(listening)

    def set_entry_text(self, text: str) -> None:
        if self._window:
            self._window.set_entry_text(text)

    def show(self) -> None:
        if self._window:
            self._window.signals.add_message.emit("", "")  # dummy to trigger Qt thread
            try:
                from PyQt6.QtCore import QMetaObject, Q_ARG, Qt as QtNS
                QMetaObject.invokeMethod(self._window, "show", QtNS.ConnectionType.QueuedConnection)
            except Exception:
                pass

    def hide(self) -> None:
        if self._window:
            try:
                from PyQt6.QtCore import QMetaObject, Qt as QtNS
                QMetaObject.invokeMethod(self._window, "hide", QtNS.ConnectionType.QueuedConnection)
            except Exception:
                pass

    def destroy(self) -> None:
        if self._app:
            try:
                self._app.quit()
            except Exception:
                pass
