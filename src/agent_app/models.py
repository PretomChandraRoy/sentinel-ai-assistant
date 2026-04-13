from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
VALID_STATUSES = {"todo", "in_progress", "done"}
@dataclass(slots=True)
class TaskCreate:
    title: str
    project_id: Optional[int] = None
@dataclass(slots=True)
class TaskStatusUpdate:
    status: str
    def validate(self) -> None:
        if self.status not in VALID_STATUSES:
            expected = ", ".join(sorted(VALID_STATUSES))
            raise ValueError(f"Invalid status '{self.status}'. Expected one of: {expected}")
