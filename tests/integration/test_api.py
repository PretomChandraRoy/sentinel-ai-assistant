from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent_app.config import AppSettings
from agent_app.dashboard.api import create_app


def test_task_flow_and_browser_consent(tmp_path: Path) -> None:
    db_path = tmp_path / "api.db"
    settings = AppSettings(db_path=str(db_path), workspace_root=str(tmp_path), polling_interval_seconds=3600)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        create_res = client.post("/api/tasks", json={"title": "API task"})
        assert create_res.status_code == 200
        task = create_res.json()

        list_res = client.get("/api/tasks")
        assert list_res.status_code == 200
        assert list_res.json()["count"] == 1

        status_res = client.post(f"/api/tasks/{task['id']}/status", json={"status": "done"})
        assert status_res.status_code == 200
        assert status_res.json()["updated"] is True

        denied = client.post("/api/browser/active-tab", json={"url": "https://example.com", "title": "Example"})
        assert denied.status_code == 403

        consent = client.post("/api/consent/browser", json={"consent": True})
        assert consent.status_code == 200

        accepted = client.post("/api/browser/active-tab", json={"url": "https://example.com", "title": "Example"})
        assert accepted.status_code == 200

        summary = client.get("/api/summary")
        assert summary.status_code == 200
        assert summary.json()["overview"]["done"] == 1


def test_link_task_to_jira(tmp_path: Path) -> None:
    db_path = tmp_path / "api.db"
    settings = AppSettings(db_path=str(db_path), workspace_root=str(tmp_path), polling_interval_seconds=3600)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        create_res = client.post("/api/tasks", json={"title": "Need Jira link"})
        assert create_res.status_code == 200
        task = create_res.json()

        link_res = client.post(f"/api/tasks/{task['id']}/jira-link", json={"issue_key": "PROJ-9"})
        assert link_res.status_code == 200
        assert link_res.json()["linked"] is True
        assert link_res.json()["issue_key"] == "PROJ-9"
