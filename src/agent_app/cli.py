from __future__ import annotations
import argparse
import json
import uvicorn
from agent_app.config import AppSettings
from agent_app.core.sync import SyncService
from agent_app.db.repository import Repository
from agent_app.integrations.git import GitAdapter
from agent_app.integrations.github_issues import GitHubIssuesAdapter
from agent_app.integrations.jira import JiraAdapter
from agent_app.integrations.workfiles import WorkfilesAdapter
from agent_app.main import app
from agent_app.models import TaskStatusUpdate
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentforpc")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    create_task = sub.add_parser("create-task")
    create_task.add_argument("title")
    create_task.add_argument("--project-id", type=int)
    create_task.add_argument("--deadline", type=str, help="Due date in YYYY-MM-DD format")
    list_tasks = sub.add_parser("list-tasks")
    list_tasks.add_argument("--project-id", type=int)
    update_status = sub.add_parser("set-status")
    update_status.add_argument("task_id", type=int)
    update_status.add_argument("status")
    sync_once = sub.add_parser("sync-once")
    sync_once.add_argument("--source", type=str)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("jarvis", help="Launch JARVIS AI assistant (system tray)")
    return parser
def run() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = AppSettings.from_env()
    repo = Repository(settings.db_path)
    repo.init_schema()
    if args.command == "init-db":
        print(json.dumps({"ok": True, "db_path": settings.db_path}))
        return
    if args.command == "create-task":
        task = repo.create_task_with_deadline(
            title=args.title, project_id=args.project_id, deadline=args.deadline
        )
        print(json.dumps(task, indent=2))
        return
    if args.command == "list-tasks":
        tasks = repo.list_tasks(project_id=args.project_id)
        print(json.dumps(tasks, indent=2))
        return
    if args.command == "set-status":
        update = TaskStatusUpdate(status=args.status)
        update.validate()
        updated = repo.update_task_status(task_id=args.task_id, status=args.status)
        print(json.dumps({"updated": updated, "task_id": args.task_id, "status": args.status}))
        return
    if args.command == "sync-once":
        adapters = {
            "jira": JiraAdapter(issue_key_resolver=repo.get_jira_issue_key),
            "github": GitHubIssuesAdapter(),
            "git": GitAdapter(workspace_root=settings.workspace_root),
            "workfiles": WorkfilesAdapter(workspace_root=settings.workspace_root, extra_folders=[]),
        }
        sync = SyncService(repo=repo, adapters=adapters)
        result = {args.source: sync.run_source(args.source)} if args.source else sync.run_all()
        print(json.dumps(result, indent=2))
        return
    if args.command == "serve":
        uvicorn.run(app, host=args.host, port=args.port)
        return
    if args.command == "jarvis":
        from agent_app.tray import launch_jarvis
        launch_jarvis(settings=settings)
        return
if __name__ == "__main__":
    run()

