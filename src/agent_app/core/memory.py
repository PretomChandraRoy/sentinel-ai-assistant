"""AI Memory — persistent long-term memory using ChromaDB vector database.

Stores conversations, tasks, notes, and activities as semantic embeddings.
When the user asks a question, relevant memories are retrieved and injected
into the AI prompt so Sentinel "remembers" everything across sessions.

All data stays local in a ChromaDB directory alongside the SQLite DB.
"""
from __future__ import annotations
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Memory types
MEMORY_CHAT = "chat"
MEMORY_TASK = "task"
MEMORY_NOTE = "note"
MEMORY_ACTIVITY = "activity"
MEMORY_SCREEN = "screen"


def _generate_id(text: str, timestamp: str) -> str:
    """Deterministic ID from content + time to avoid duplicates."""
    raw = f"{text}|{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class MemoryManager:
    """Long-term semantic memory backed by ChromaDB.

    Stores text chunks with metadata and retrieves the most relevant
    memories for a given query using cosine similarity on embeddings.
    """

    def __init__(
        self,
        persist_dir: str = ".sentinel_memory",
        collection_name: str = "sentinel_memories",
    ) -> None:
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._collection = None  # type: ignore[assignment]
        self._client = None  # type: ignore[assignment]
        self._ready = False

    def init(self) -> bool:
        """Initialize ChromaDB client and collection. Returns True if successful."""
        try:
            import chromadb

            # Ensure persist directory exists
            os.makedirs(self._persist_dir, exist_ok=True)

            self._client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            count = self._collection.count()
            logger.info(
                "MemoryManager initialized: %d memories in %s",
                count, self._persist_dir,
            )
            self._ready = True
            return True
        except Exception as exc:
            logger.warning("MemoryManager init failed (non-critical): %s", exc)
            self._ready = False
            return False

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def count(self) -> int:
        if not self._ready:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0

    # ---- Store memories ----

    def store(
        self,
        text: str,
        memory_type: str = MEMORY_CHAT,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> bool:
        """Store a text chunk as a memory. Returns True on success."""
        if not self._ready or not text or len(text.strip()) < 5:
            return False

        ts = timestamp or datetime.now(timezone.utc).isoformat()
        doc_id = _generate_id(text, ts)

        meta = {
            "type": memory_type,
            "timestamp": ts,
            "length": len(text),
        }
        if metadata:
            # ChromaDB metadata values must be str, int, float, or bool
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v

        try:
            self._collection.upsert(
                ids=[doc_id],
                documents=[text[:2000]],  # Cap at 2000 chars per chunk
                metadatas=[meta],
            )
            return True
        except Exception as exc:
            logger.debug("Memory store failed: %s", exc)
            return False

    def store_conversation(self, role: str, content: str) -> bool:
        """Store a chat message (user or assistant) as a memory."""
        prefix = "User said" if role == "user" else "Sentinel replied"
        text = f"{prefix}: {content}"
        return self.store(
            text=text,
            memory_type=MEMORY_CHAT,
            metadata={"role": role},
        )

    def store_task_event(self, event: str, task_title: str, task_id: int = 0) -> bool:
        """Store a task lifecycle event as a memory."""
        text = f"Task {event}: \"{task_title}\" (id:{task_id})"
        return self.store(
            text=text,
            memory_type=MEMORY_TASK,
            metadata={"event": event, "task_id": task_id},
        )

    def store_note(self, note: str) -> bool:
        """Store a user note or important piece of information."""
        return self.store(text=note, memory_type=MEMORY_NOTE)

    # ---- Retrieve memories ----

    def recall(
        self,
        query: str,
        n_results: int = 5,
        memory_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve the most relevant memories for a query.

        Returns list of dicts with keys: text, type, timestamp, distance.
        Lower distance = more relevant.
        """
        if not self._ready or not query:
            return []

        where_filter = None
        if memory_type:
            where_filter = {"type": memory_type}

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(n_results, self.count or 1),
                where=where_filter,
            )
        except Exception as exc:
            logger.debug("Memory recall failed: %s", exc)
            return []

        memories = []
        if results and results.get("documents"):
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, dists):
                memories.append({
                    "text": doc,
                    "type": meta.get("type", "unknown"),
                    "timestamp": meta.get("timestamp", ""),
                    "distance": round(dist, 4),
                })

        return memories

    def recall_formatted(
        self,
        query: str,
        n_results: int = 5,
        max_chars: int = 1500,
    ) -> str:
        """Retrieve relevant memories and format them for the AI prompt."""
        memories = self.recall(query, n_results=n_results)
        if not memories:
            return ""

        lines = []
        total_chars = 0
        for mem in memories:
            # Skip very distant (irrelevant) results
            if mem["distance"] > 1.5:
                continue
            text = mem["text"]
            ts = mem["timestamp"][:10] if mem["timestamp"] else ""
            line = f"[{ts}] {text}"
            if total_chars + len(line) > max_chars:
                break
            lines.append(line)
            total_chars += len(line)

        return "\n".join(lines)

    # ---- Maintenance ----

    def get_stats(self) -> Dict[str, Any]:
        """Return memory statistics."""
        if not self._ready:
            return {"ready": False, "count": 0}

        count = self.count
        return {
            "ready": True,
            "count": count,
            "persist_dir": self._persist_dir,
        }

    def clear_all(self) -> bool:
        """Delete all memories. Use with caution."""
        if not self._ready:
            return False
        try:
            self._client.delete_collection(self._collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("All memories cleared.")
            return True
        except Exception as exc:
            logger.warning("Memory clear failed: %s", exc)
            return False
