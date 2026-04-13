from __future__ import annotations

from agent_app.monitors.system_monitor import capture_snapshot, snapshot_to_dict


def test_capture_snapshot_returns_valid_data() -> None:
    snap = capture_snapshot()
    assert 0 <= snap.cpu_percent <= 100
    assert 0 <= snap.ram_percent <= 100
    assert snap.ram_total_gb > 0
    assert snap.disk_free_gb >= 0
    assert isinstance(snap.active_window, str)
    assert isinstance(snap.timestamp, str)


def test_snapshot_to_dict() -> None:
    snap = capture_snapshot()
    d = snapshot_to_dict(snap)
    assert "cpu_percent" in d
    assert "ram_percent" in d
    assert "disk_free_gb" in d
    assert "active_window" in d
    assert "timestamp" in d
    assert "battery_percent" in d
    assert "top_processes" in d
    assert isinstance(d["top_processes"], list)
