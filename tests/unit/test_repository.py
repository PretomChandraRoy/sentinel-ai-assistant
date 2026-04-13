from __future__ import annotations

from pathlib import Path

from agent_app.db.repository import Repository


def test_inbox_project_and_task_lifecycle(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    repo = Repository(str(db_path))
    repo.init_schema()

    task = repo.create_task("Write tests")
    assert task["title"] == "Write tests"
    assert task["status"] == "todo"

    updated = repo.update_task_status(task_id=int(task["id"]), status="done")
    assert updated is True

    tasks = repo.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["status"] == "done"


def test_dashboard_counts(tmp_path: Path) -> None:
    repo = Repository(str(tmp_path / "test.db"))
    repo.init_schema()
    one = repo.create_task("A")
    two = repo.create_task("B")
    repo.update_task_status(int(one["id"]), "in_progress")
    repo.update_task_status(int(two["id"]), "done")

    summary = repo.dashboard_overview()
    assert summary["todo"] == 0
    assert summary["in_progress"] == 1
    assert summary["done"] == 1
    assert summary["total"] == 2


def test_jira_link_roundtrip(tmp_path: Path) -> None:
    repo = Repository(str(tmp_path / "test.db"))
    repo.init_schema()

    task = repo.create_task("Link me")
    task_id = int(task["id"])

    assert repo.get_jira_issue_key(task_id) is None

    linked = repo.link_jira_issue(task_id=task_id, issue_key="PROJ-123")
    assert linked is True
    assert repo.get_jira_issue_key(task_id) == "PROJ-123"

    relinked = repo.link_jira_issue(task_id=task_id, issue_key="PROJ-124")
    assert relinked is True
    assert repo.get_jira_issue_key(task_id) == "PROJ-124"
