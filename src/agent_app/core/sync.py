from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
from agent_app.db.repository import Repository
from agent_app.integrations.base import IntegrationAdapter
@dataclass(slots=True)
class SyncService:
    repo: Repository
    adapters: Dict[str, IntegrationAdapter]
    def run_source(self, source: str) -> int:
        adapter = self.adapters.get(source)
        if not adapter:
            return 0
        events = adapter.fetch()
        for event in events:
            self.repo.add_progress(source=event.source, content=event.content, task_id=None)
            self.repo.upsert_sync_cursor(source=event.source, cursor_value=event.cursor)
        return len(events)
    def run_all(self) -> Dict[str, int]:
        results: Dict[str, int] = {}
        for source in self.adapters:
            results[source] = self.run_source(source)
        return results
    def push_task_status(self, source: str, task_id: int, status: str) -> tuple[bool, str]:
        adapter = self.adapters.get(source)
        if not adapter:
            return False, "Unknown source: " + source
        success, message = adapter.push_task_update(task_id=task_id, status=status)
        if not success:
            self.repo.enqueue_retry_job(
                source=source,
                action="push_task_update",
                payload={"task_id": task_id, "status": status},
                error=message,
            )
        return success, message
