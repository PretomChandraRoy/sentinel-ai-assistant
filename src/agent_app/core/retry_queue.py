from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Dict
from agent_app.db.repository import Repository
from agent_app.integrations.base import IntegrationAdapter
@dataclass(slots=True)
class RetryQueueService:
    repo: Repository
    adapters: Dict[str, IntegrationAdapter]
    def process_due_jobs(self) -> int:
        jobs = self.repo.due_retry_jobs()
        processed = 0
        for job in jobs:
            source = job["source"]
            adapter = self.adapters.get(source)
            if not adapter:
                self.repo.mark_retry_job(int(job["id"]), success=False, error="adapter missing")
                processed += 1
                continue
            payload = json.loads(job["payload"])
            task_id = int(payload.get("task_id", 0))
            status = str(payload.get("status", ""))
            success, message = adapter.push_task_update(task_id=task_id, status=status)
            self.repo.mark_retry_job(int(job["id"]), success=success, error=message)
            processed += 1
        return processed
