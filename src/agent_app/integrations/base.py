from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol
@dataclass(slots=True)
class SyncEvent:
    source: str
    content: str
    cursor: Optional[str] = None
class IntegrationAdapter(Protocol):
    source: str
    def fetch(self) -> list[SyncEvent]:
        ...
    def push_task_update(self, task_id: int, status: str) -> tuple[bool, str]:
        ...
