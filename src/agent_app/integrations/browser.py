from __future__ import annotations
from dataclasses import dataclass
@dataclass(slots=True)
class BrowserAdapter:
    source: str = "browser"
    def normalize(self, url: str, title: str) -> tuple[str, str]:
        return url.strip(), title.strip()
    def push_task_update(self, task_id: int, status: str) -> tuple[bool, str]:
        return True, "Browser adapter does not push task state"
