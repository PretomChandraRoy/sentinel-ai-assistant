from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from agent_app.config import AppSettings
from agent_app.core.credentials import CredentialStore
from agent_app.core.orchestrator import SyncOrchestrator
from agent_app.core.retry_queue import RetryQueueService
from agent_app.core.sync import SyncService
from agent_app.db.repository import Repository
from agent_app.integrations.browser import BrowserAdapter
from agent_app.integrations.git import GitAdapter
from agent_app.integrations.github_issues import GitHubIssuesAdapter
from agent_app.integrations.jira import JiraAdapter
from agent_app.integrations.workfiles import WorkfilesAdapter
from agent_app.models import TaskStatusUpdate
class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    project_id: Optional[int] = None
class TaskStatusRequest(BaseModel):
    status: str
class BrowserConsentRequest(BaseModel):
    consent: bool
class BrowserActiveTabRequest(BaseModel):
    url: str = Field(min_length=1)
    title: str = Field(min_length=1)
class SecretRequest(BaseModel):
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
class JiraLinkRequest(BaseModel):
    issue_key: str = Field(min_length=2)
def _build_templates() -> Jinja2Templates:
    templates_dir = Path(__file__).resolve().parent / "templates"
    return Jinja2Templates(directory=str(templates_dir))
def create_app(settings: Optional[AppSettings] = None) -> FastAPI:
    resolved = settings or AppSettings.from_env()
    repo = Repository(resolved.db_path)
    repo.init_schema()
    adapters = {
        "jira": JiraAdapter(issue_key_resolver=repo.get_jira_issue_key),
        "github": GitHubIssuesAdapter(),
        "git": GitAdapter(workspace_root=resolved.workspace_root),
        "workfiles": WorkfilesAdapter(workspace_root=resolved.workspace_root, extra_folders=[]),
    }
    sync_service = SyncService(repo=repo, adapters=adapters)
    retry_service = RetryQueueService(repo=repo, adapters=adapters)
    orchestrator = SyncOrchestrator(
        sync_service=sync_service,
        retry_service=retry_service,
        interval_seconds=resolved.polling_interval_seconds,
    )
    browser_adapter = BrowserAdapter()
    credentials = CredentialStore()
    app = FastAPI(title="AgentForPC", version="0.1.0")
    templates = _build_templates()
    app.state.repo = repo
    app.state.orchestrator = orchestrator
    app.state.browser_consent = False
    app.state.browser_adapter = browser_adapter
    app.state.credentials = credentials
    @app.on_event("startup")
    def startup_event() -> None:
        app.state.browser_consent = False
        app.state.orchestrator.start()
    @app.on_event("shutdown")
    def shutdown_event() -> None:
        repo.create_daily_snapshot(project_id=None)
        app.state.orchestrator.stop()
    @app.get("/")
    def root() -> dict[str, str]:
        return {"status": "ok", "app": "AgentForPC"}
    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        overview = repo.dashboard_overview()
        tasks = repo.list_tasks()[:30]
        progress = repo.recent_progress(limit=20)
        browser_events = repo.recent_browser_events(limit=10)
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "overview": overview,
                "tasks": tasks,
                "progress": progress,
                "browser_events": browser_events,
                "browser_consent": app.state.browser_consent,
            },
        )
    @app.post("/api/tasks")
    def create_task(payload: TaskCreateRequest) -> dict:
        return repo.create_task(title=payload.title, project_id=payload.project_id)
    @app.get("/api/tasks")
    def list_tasks(
        project_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        tasks = repo.list_tasks(project_id=project_id, start_date=start_date, end_date=end_date)
        return {"items": tasks, "count": len(tasks)}
    @app.post("/api/tasks/{task_id}/status")
    def update_task_status(task_id: int, payload: TaskStatusRequest) -> dict:
        update = TaskStatusUpdate(status=payload.status)
        update.validate()
        changed = repo.update_task_status(task_id=task_id, status=payload.status)
        if not changed:
            raise HTTPException(status_code=404, detail="Task not found")
        ok, message = sync_service.push_task_status("jira", task_id=task_id, status=payload.status)
        return {"updated": True, "jira_sync_ok": ok, "jira_message": message}
    @app.get("/api/summary")
    def get_summary(
        project_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        overview = repo.dashboard_overview(project_id=project_id)
        tasks = repo.list_tasks(project_id=project_id, start_date=start_date, end_date=end_date)
        return {"overview": overview, "tasks": tasks}
    @app.post("/api/consent/browser")
    def set_browser_consent(payload: BrowserConsentRequest) -> dict:
        app.state.browser_consent = payload.consent
        return {"browser_consent": app.state.browser_consent}
    @app.post("/api/browser/active-tab")
    def ingest_active_tab(payload: BrowserActiveTabRequest) -> dict:
        if not app.state.browser_consent:
            raise HTTPException(status_code=403, detail="Browser consent is not granted for this session")
        url, title = browser_adapter.normalize(payload.url, payload.title)
        repo.record_browser_event(url=url, title=title)
        repo.add_progress(source="browser", content="Active tab: {0} ({1})".format(title, url))
        return {"saved": True}
    @app.post("/api/sync/trigger")
    def trigger_sync(source: Optional[str] = None) -> dict:
        return app.state.orchestrator.trigger_sync(source=source)
    @app.post("/webhook/{source}")
    def webhook(source: str) -> dict:
        return app.state.orchestrator.trigger_sync(source=source)
    @app.post("/api/secrets")
    def store_secret(payload: SecretRequest) -> dict:
        credentials.set_secret(payload.name, payload.value)
        return {"stored": True, "name": payload.name}
    @app.post("/api/tasks/{task_id}/jira-link")
    def link_task_to_jira(task_id: int, payload: JiraLinkRequest) -> dict:
        linked = repo.link_jira_issue(task_id=task_id, issue_key=payload.issue_key.strip())
        if not linked:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"linked": True, "task_id": task_id, "issue_key": payload.issue_key.strip()}

    # ---- JARVIS API endpoints ----

    class ChatRequest(BaseModel):
        message: str = Field(min_length=1)

    @app.post("/api/chat")
    def api_chat(payload: ChatRequest) -> dict:
        from agent_app.core.brain import JarvisBrain
        from datetime import datetime, timezone as tz
        brain = getattr(app.state, "brain", None)
        if brain is None:
            brain = JarvisBrain()
            app.state.brain = brain
        overview = repo.dashboard_overview()
        tasks = repo.list_tasks()[:10]
        activity = repo.recent_progress(limit=10)
        now = datetime.now(tz.utc).strftime("%Y-%m-%d %H:%M UTC")
        response = brain.chat(
            user_message=payload.message,
            task_overview=overview,
            recent_tasks=tasks,
            recent_activity=activity,
            current_time=now,
        )
        repo.save_chat_message("user", payload.message)
        repo.save_chat_message("assistant", response)
        return {"role": "assistant", "content": response}

    @app.get("/api/system/status")
    def system_status() -> dict:
        from agent_app.monitors.system_monitor import capture_snapshot, snapshot_to_dict
        snap = capture_snapshot()
        return snapshot_to_dict(snap)

    @app.get("/api/chat/history")
    def chat_history(limit: int = 50) -> dict:
        messages = repo.get_chat_history(limit=limit)
        return {"messages": messages, "count": len(messages)}

    @app.get("/api/notifications")
    def get_notifications() -> dict:
        notes = repo.get_unread_notifications()
        return {"notifications": notes, "count": len(notes)}

    return app

