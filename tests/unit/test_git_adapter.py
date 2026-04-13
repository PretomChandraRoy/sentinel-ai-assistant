from __future__ import annotations

from agent_app.integrations.git import GitAdapter


def test_parse_git_log() -> None:
    raw = "abc12345|Alice|Initial commit\n98765432|Bob|Fix bug"
    events = GitAdapter.parse_git_log(raw)
    assert len(events) == 2
    assert events[0].source == "git"
    assert "Initial commit" in events[0].content
    assert events[1].cursor == "98765432"

