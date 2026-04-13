from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Callable, Optional
import httpx
from agent_app.integrations.base import SyncEvent
@dataclass(slots=True)
class JiraAdapter:
    source: str = "jira"
    issue_key_resolver: Optional[Callable[[int], Optional[str]]] = None
    def _config(self) -> tuple[str, str, str] | None:
        base_url = os.getenv("JIRA_BASE_URL", "").rstrip("/")
        email = os.getenv("JIRA_EMAIL", "")
        token = os.getenv("JIRA_API_TOKEN", "")
        if not base_url or not email or not token:
            return None
        return base_url, email, token
    def _status_candidates(self, status: str) -> list[str]:
        mapping = {
            "todo": ["To Do", "Open", "Selected for Development"],
            "in_progress": ["In Progress", "In Development"],
            "done": ["Done", "Closed", "Resolved"],
        }
        return mapping.get(status, [status])
    def fetch(self) -> list[SyncEvent]:
        cfg = self._config()
        if not cfg:
            return []
        base_url, email, token = cfg
        jql = os.getenv("JIRA_JQL", "assignee=currentUser() ORDER BY updated DESC")
        url = base_url + "/rest/api/3/search"
        params = {
            "jql": jql,
            "maxResults": 20,
            "fields": "summary,status",
        }
        try:
            response = httpx.get(url, params=params, auth=(email, token), timeout=20.0)
            response.raise_for_status()
        except Exception:
            return []
        payload = response.json()
        events: list[SyncEvent] = []
        for issue in payload.get("issues", []):
            key = issue.get("key", "")
            fields = issue.get("fields", {})
            summary = fields.get("summary", "")
            status_name = (fields.get("status") or {}).get("name", "")
            content = "[{0}] {1} :: {2}".format(key, summary, status_name)
            events.append(SyncEvent(source=self.source, content=content, cursor=key or None))
        return events
    def push_task_update(self, task_id: int, status: str) -> tuple[bool, str]:
        cfg = self._config()
        if not cfg:
            return False, "Jira credentials are missing (JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN)"
        base_url, email, token = cfg
        issue_key = None
        if self.issue_key_resolver:
            issue_key = self.issue_key_resolver(task_id)
        issue_key = issue_key or os.getenv("JIRA_DEFAULT_ISSUE_KEY", "").strip()
        if not issue_key:
            return False, "No Jira issue linked to this task"
        transitions_url = base_url + "/rest/api/3/issue/{0}/transitions".format(issue_key)
        try:
            transitions_res = httpx.get(transitions_url, auth=(email, token), timeout=20.0)
            transitions_res.raise_for_status()
        except Exception as exc:
            return False, "Failed to read Jira transitions: {0}".format(exc)
        desired_names = {name.casefold() for name in self._status_candidates(status)}
        transitions = transitions_res.json().get("transitions", [])
        selected_transition_id = None
        available_names: list[str] = []
        for item in transitions:
            name = str(item.get("name", ""))
            available_names.append(name)
            if name.casefold() in desired_names:
                selected_transition_id = str(item.get("id", ""))
                break
        if not selected_transition_id:
            return (
                False,
                "No Jira transition matched status '{0}'. Available: {1}".format(
                    status,
                    ", ".join(available_names) if available_names else "none",
                ),
            )
        try:
            update_res = httpx.post(
                transitions_url,
                auth=(email, token),
                json={"transition": {"id": selected_transition_id}},
                timeout=20.0,
            )
            update_res.raise_for_status()
        except Exception as exc:
            return False, "Failed to push Jira status update: {0}".format(exc)
        return True, "Jira issue {0} moved to {1}".format(issue_key, status)
