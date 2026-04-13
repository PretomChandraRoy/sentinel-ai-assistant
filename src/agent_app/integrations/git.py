from __future__ import annotations
import subprocess
from dataclasses import dataclass
from agent_app.integrations.base import SyncEvent
@dataclass(slots=True)
class GitAdapter:
    workspace_root: str
    source: str = "git"
    @staticmethod
    def parse_git_log(raw_output: str) -> list[SyncEvent]:
        delimiter = chr(124)
        events: list[SyncEvent] = []
        for line in raw_output.splitlines():
            parts = line.strip().split(delimiter, 2)
            if len(parts) != 3:
                continue
            commit_hash, author, message = parts
            content = "[{0}] {1} ({2})".format(author, message, commit_hash[:8])
            events.append(SyncEvent(source="git", content=content, cursor=commit_hash))
        return events
    def fetch(self) -> list[SyncEvent]:
        sep = "%x1f"
        cmd = [
            "git",
            "-C",
            self.workspace_root,
            "--no-pager",
            "log",
            "--since=1 day ago",
            "--pretty=format:%H" + sep + "%an" + sep + "%s",
            "-n",
            "25",
        ]
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        except Exception:
            return []
        normalized = output.replace(chr(31), chr(124))
        return self.parse_git_log(normalized)
    def push_task_update(self, task_id: int, status: str) -> tuple[bool, str]:
        return True, "git adapter does not push task state"
