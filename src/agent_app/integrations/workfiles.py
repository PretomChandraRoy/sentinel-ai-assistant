from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from agent_app.integrations.base import SyncEvent
@dataclass(slots=True)
class WorkfilesAdapter:
    workspace_root: str
    extra_folders: list[str] = field(default_factory=list)
    source: str = "workfiles"
    def _iter_roots(self) -> list[Path]:
        roots = [Path(self.workspace_root)]
        roots.extend(Path(folder) for folder in self.extra_folders if folder)
        seen: set[str] = set()
        unique_roots: list[Path] = []
        for root in roots:
            key = str(root.resolve()) if root.exists() else str(root)
            if key in seen:
                continue
            seen.add(key)
            unique_roots.append(root)
        return unique_roots
    def fetch(self) -> list[SyncEvent]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        events: list[SyncEvent] = []
        for root in self._iter_roots():
            if not root.exists():
                continue
            for file_path in root.rglob("*"):
                if not file_path.is_file():
                    continue
                if any(part in {".venv", ".git", "__pycache__"} for part in file_path.parts):
                    continue
                try:
                    modified = datetime.fromtimestamp(file_path.stat().st_mtime, timezone.utc)
                except OSError:
                    continue
                if modified < cutoff:
                    continue
                rel = file_path.relative_to(root) if str(file_path).startswith(str(root)) else file_path
                content = "Modified file: {0}".format(rel)
                events.append(SyncEvent(source=self.source, content=content, cursor=str(file_path)))
                if len(events) >= 100:
                    return events
        return events
    def push_task_update(self, task_id: int, status: str) -> tuple[bool, str]:
        return True, "workfiles adapter does not push task state"
