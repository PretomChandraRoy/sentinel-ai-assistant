from __future__ import annotations
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from agent_app.core.retry_queue import RetryQueueService
from agent_app.core.sync import SyncService
@dataclass
class SyncOrchestrator:
    sync_service: SyncService
    retry_service: RetryQueueService
    interval_seconds: int
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)
    def start(self) -> None:
        self.sync_service.run_all()
        self.retry_service.process_due_jobs()
        self._thread = threading.Thread(target=self._loop, name="sync-loop", daemon=True)
        self._thread.start()
    def _loop(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            self.sync_service.run_all()
            self.retry_service.process_due_jobs()
    def trigger_sync(self, source: Optional[str] = None) -> Dict[str, int]:
        if source:
            return {source: self.sync_service.run_source(source)}
        return self.sync_service.run_all()
    def stop(self, timeout_seconds: float = 2.0) -> None:
        self._stop_event.set()
        self.retry_service.process_due_jobs()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout_seconds)
        time.sleep(0.05)
