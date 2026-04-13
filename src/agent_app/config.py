from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
@dataclass(slots=True)
class AppSettings:
    db_path: str
    workspace_root: str
    polling_interval_seconds: int = 900
    @classmethod
    def from_env(cls) -> "AppSettings":
        workspace = os.getenv("AGENT_WORKSPACE_ROOT", str(Path.cwd()))
        db_path = os.getenv("AGENT_DB_PATH", str(Path(workspace) / ".agentforpc.db"))
        interval = int(os.getenv("AGENT_POLLING_SECONDS", "900"))
        return cls(db_path=db_path, workspace_root=workspace, polling_interval_seconds=interval)
