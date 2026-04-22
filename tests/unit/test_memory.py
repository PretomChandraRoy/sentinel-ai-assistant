"""Tests for the AI memory (RAG) module."""
import os
import shutil
import uuid
from agent_app.core.memory import (
    MemoryManager,
    MEMORY_CHAT,
    MEMORY_TASK,
    MEMORY_NOTE,
    _generate_id,
)

# Use a shared temp dir for all tests in this file
_TEST_MEM_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "_test_memory_tmp"
)


def _make_memory() -> MemoryManager:
    """Create a MemoryManager with a unique collection to avoid cross-test leaks."""
    os.makedirs(_TEST_MEM_DIR, exist_ok=True)
    unique_name = f"test_{uuid.uuid4().hex[:8]}"
    mm = MemoryManager(persist_dir=_TEST_MEM_DIR, collection_name=unique_name)
    mm.init()
    return mm


def teardown_module():
    """Clean up temp directory after all tests in this module."""
    if os.path.exists(_TEST_MEM_DIR):
        shutil.rmtree(_TEST_MEM_DIR, ignore_errors=True)


def test_init_success():
    mm = _make_memory()
    assert mm.is_ready
    assert mm.count == 0


def test_store_and_recall():
    mm = _make_memory()
    mm.store("I am working on the Sentinel AI project", memory_type=MEMORY_CHAT)
    mm.store("My deadline for the report is next Friday", memory_type=MEMORY_CHAT)
    mm.store("I prefer dark mode in all my editors", memory_type=MEMORY_NOTE)

    results = mm.recall("What project am I working on?", n_results=3)
    assert len(results) > 0
    assert any("Sentinel" in r["text"] for r in results)


def test_store_conversation():
    mm = _make_memory()
    mm.store_conversation("user", "Tell me about my tasks")
    mm.store_conversation("assistant", "You have 3 pending tasks")
    assert mm.count == 2


def test_store_task_event():
    mm = _make_memory()
    mm.store_task_event("created", "Fix login bug", task_id=42)
    results = mm.recall("login bug")
    assert len(results) == 1
    assert "login bug" in results[0]["text"].lower()


def test_recall_empty_returns_empty():
    mm = _make_memory()
    results = mm.recall("anything")
    assert results == []


def test_recall_formatted():
    mm = _make_memory()
    mm.store("The meeting is at 3pm tomorrow", memory_type=MEMORY_NOTE)
    formatted = mm.recall_formatted("meeting time")
    assert "3pm" in formatted


def test_skip_short_text():
    mm = _make_memory()
    result = mm.store("Hi")  # Too short (< 5 chars)
    assert result is False
    assert mm.count == 0


def test_stats():
    mm = _make_memory()
    mm.store("test memory content here")
    stats = mm.get_stats()
    assert stats["ready"] is True
    assert stats["count"] == 1


def test_clear_all():
    mm = _make_memory()
    mm.store("memory 1 content here")
    mm.store("memory 2 content here")
    assert mm.count == 2
    mm.clear_all()
    assert mm.count == 0


def test_generate_id_deterministic():
    id1 = _generate_id("hello", "2026-01-01")
    id2 = _generate_id("hello", "2026-01-01")
    id3 = _generate_id("world", "2026-01-01")
    assert id1 == id2
    assert id1 != id3


def test_memory_manager_not_ready_graceful():
    mm = MemoryManager(persist_dir="/nonexistent/path/xyz")
    assert not mm.is_ready
    assert mm.count == 0
    assert mm.recall("test") == []
    assert mm.recall_formatted("test") == ""
    assert mm.store("test content") is False
