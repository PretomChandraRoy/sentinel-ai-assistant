from __future__ import annotations
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import psutil

try:
    import pygetwindow as gw
except Exception:
    gw = None  # type: ignore[assignment]


@dataclass
class SystemSnapshot:
    timestamp: str
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    ram_total_gb: float
    disk_percent: float
    disk_free_gb: float
    battery_percent: Optional[float]
    battery_charging: Optional[bool]
    active_window: str
    top_processes: List[Dict[str, Any]]


def capture_snapshot() -> SystemSnapshot:
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    battery = psutil.sensors_battery()
    battery_pct = battery.percent if battery else None
    battery_charging = battery.power_plugged if battery else None

    active_window = ""
    if gw is not None:
        try:
            win = gw.getActiveWindow()
            if win and win.title:
                active_window = win.title
        except Exception:
            pass

    top_procs: List[Dict[str, Any]] = []
    try:
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            info = proc.info  # type: ignore[attr-defined]
            if info and info.get("cpu_percent", 0) is not None:
                top_procs.append(info)
        top_procs.sort(key=lambda p: p.get("cpu_percent", 0) or 0, reverse=True)
        top_procs = top_procs[:5]
    except Exception:
        pass

    return SystemSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        cpu_percent=cpu,
        ram_percent=mem.percent,
        ram_used_gb=round(mem.used / (1024 ** 3), 1),
        ram_total_gb=round(mem.total / (1024 ** 3), 1),
        disk_percent=disk.percent,
        disk_free_gb=round(disk.free / (1024 ** 3), 1),
        battery_percent=battery_pct,
        battery_charging=battery_charging,
        active_window=active_window,
        top_processes=top_procs,
    )


def snapshot_to_dict(snap: SystemSnapshot) -> Dict[str, Any]:
    return {
        "timestamp": snap.timestamp,
        "cpu_percent": snap.cpu_percent,
        "ram_percent": snap.ram_percent,
        "ram_used_gb": snap.ram_used_gb,
        "ram_total_gb": snap.ram_total_gb,
        "disk_percent": snap.disk_percent,
        "disk_free_gb": snap.disk_free_gb,
        "battery_percent": snap.battery_percent,
        "battery_charging": snap.battery_charging,
        "active_window": snap.active_window,
        "top_processes": snap.top_processes,
    }


AlertCallback = Callable[[str, str], None]


@dataclass
class SystemMonitor:
    interval_seconds: int = 30
    on_alert: Optional[AlertCallback] = None
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)
    _latest: Optional[SystemSnapshot] = field(default=None, init=False)

    def start(self) -> None:
        self._latest = capture_snapshot()
        self._check_alerts(self._latest)
        self._thread = threading.Thread(target=self._loop, name="sys-monitor", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            try:
                self._latest = capture_snapshot()
                self._check_alerts(self._latest)
            except Exception:
                pass

    def get_latest(self) -> Optional[SystemSnapshot]:
        return self._latest

    def _check_alerts(self, snap: SystemSnapshot) -> None:
        if self.on_alert is None:
            return
        if snap.battery_percent is not None and snap.battery_percent <= 15 and not snap.battery_charging:
            self.on_alert("battery_low", f"Battery is at {snap.battery_percent}%! Plug in your charger.")
        if snap.cpu_percent >= 90:
            self.on_alert("high_cpu", f"CPU usage is at {snap.cpu_percent}%!")
        if snap.ram_percent >= 90:
            self.on_alert("high_ram", f"RAM usage is at {snap.ram_percent}% ({snap.ram_used_gb}GB / {snap.ram_total_gb}GB)")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
