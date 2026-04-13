from __future__ import annotations
import os
from dataclasses import dataclass
from agent_app.integrations.base import SyncEvent
@dataclass(slots=True)
class GitHubIssuesAdapter:
    source: str = "github"
    def fetch(self) -> list[SyncEvent]:
        if not os.getenv("GITHUB_REPO"):
            return []
        repo = os.getenv("GITHUB_REPO", "")
        return [SyncEvent(source=self.source, content="GitHub issues integration ready for " + repo, cursor=None)]
    def push_task_update(self, task_id: int, status: str) -> tuple[bool, str]:
        return True, "GitHub push disabled in MVP by design"
