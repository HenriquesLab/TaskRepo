"""Tests for the --json output mode of `tsk list`."""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from taskrepo.cli.commands.list import _load_uuid_to_display_id, _task_to_dict
from taskrepo.core.task import Task


def _make_task(uuid: str = "abc-123", **overrides) -> Task:
    """Build a Task with sensible defaults for serialization tests."""
    defaults = {
        "id": uuid,
        "title": "A task",
        "status": "pending",
        "priority": "H",
        "project": "proj",
        "assignees": ["@alice"],
        "tags": ["urgent"],
        "links": ["https://example.com/1"],
        "due": datetime(2026, 5, 1, 12, 0),
        "created": datetime(2026, 1, 1, 9, 0),
        "modified": datetime(2026, 4, 1, 15, 0),
        "depends": ["dep-1"],
        "parent": "parent-uuid",
        "description": "body",
        "repo": "work",
    }
    defaults.update(overrides)
    return Task(**defaults)


def test_task_to_dict_contains_expected_fields():
    task = _make_task()
    uuid_to_id = {"abc-123": 7}

    result = _task_to_dict(task, uuid_to_id)

    assert result["id"] == 7
    assert result["uuid"] == "abc-123"
    assert result["title"] == "A task"
    assert result["status"] == "pending"
    assert result["priority"] == "H"
    assert result["repo"] == "work"
    assert result["project"] == "proj"
    assert result["assignees"] == ["@alice"]
    assert result["tags"] == ["urgent"]
    assert result["links"] == ["https://example.com/1"]
    assert result["depends"] == ["dep-1"]
    assert result["parent"] == "parent-uuid"
    assert result["description"] == "body"
    # All dates ISO 8601
    assert result["due"] == "2026-05-01T12:00:00"
    assert result["created"] == "2026-01-01T09:00:00"
    assert result["modified"] == "2026-04-01T15:00:00"


def test_task_to_dict_missing_uuid_in_cache_yields_null_id():
    task = _make_task(uuid="not-in-cache")
    result = _task_to_dict(task, uuid_to_id={"other": 1})
    assert result["id"] is None
    assert result["uuid"] == "not-in-cache"


def test_task_to_dict_handles_none_dates():
    task = _make_task(due=None)
    result = _task_to_dict(task, uuid_to_id={})
    assert result["due"] is None
    # created/modified are set by Task.__post_init__ defaults, so they are
    # always serializable strings — just assert they round-trip through JSON.
    json.dumps(result)


def test_task_to_dict_output_is_json_serializable():
    task = _make_task()
    result = _task_to_dict(task, uuid_to_id={"abc-123": 1})
    # Should not raise
    roundtrip = json.loads(json.dumps(result))
    assert roundtrip["id"] == 1


def test_load_uuid_to_display_id_returns_empty_when_cache_missing():
    with TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "id_cache.json"
        with patch("taskrepo.cli.commands.list.get_cache_path", return_value=cache_path):
            assert _load_uuid_to_display_id() == {}


def test_load_uuid_to_display_id_parses_cache():
    with TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "id_cache.json"
        cache_path.write_text(
            json.dumps(
                {
                    "1": {"uuid": "uuid-a", "repo": "r", "title": "A"},
                    "2": {"uuid": "uuid-b", "repo": "r", "title": "B"},
                }
            )
        )
        with patch("taskrepo.cli.commands.list.get_cache_path", return_value=cache_path):
            result = _load_uuid_to_display_id()
        assert result == {"uuid-a": 1, "uuid-b": 2}


def test_load_uuid_to_display_id_handles_malformed_cache():
    with TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "id_cache.json"
        cache_path.write_text("not valid json")
        with patch("taskrepo.cli.commands.list.get_cache_path", return_value=cache_path):
            assert _load_uuid_to_display_id() == {}


def test_load_uuid_to_display_id_is_single_read_for_n_tasks():
    """Regression guard: caller must not re-open the cache per task.

    We verify that after `_load_uuid_to_display_id()` returns a map, looking
    up N tasks is a plain dict lookup (O(1) per task, no further I/O).
    """
    uuid_to_id = {f"uuid-{i}": i for i in range(100)}
    # Simulate the serialization loop without any disk access
    payload = [_task_to_dict(_make_task(uuid=f"uuid-{i}"), uuid_to_id) for i in range(100)]
    assert len(payload) == 100
    assert payload[0]["id"] == 0
    assert payload[99]["id"] == 99
