"""Unit tests for Task model."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from taskrepo.core.task import Task


def test_task_creation():
    """Test basic task creation."""
    task = Task(
        id="001",
        title="Test task",
        status="pending",
        priority="H",
        project="test-project",
        assignees=["@user1", "@user2"],
        tags=["bug", "urgent"],
    )

    assert task.id == "001"
    assert task.title == "Test task"
    assert task.status == "pending"
    assert task.priority == "H"
    assert task.project == "test-project"
    assert task.assignees == ["@user1", "@user2"]
    assert task.tags == ["bug", "urgent"]


def test_task_invalid_status():
    """Test that invalid status raises ValueError."""
    with pytest.raises(ValueError, match="Invalid status"):
        Task(id="001", title="Test", status="invalid")


def test_task_invalid_priority():
    """Test that invalid priority raises ValueError."""
    with pytest.raises(ValueError, match="Invalid priority"):
        Task(id="001", title="Test", priority="X")


def test_task_to_markdown():
    """Test converting task to markdown."""
    task = Task(
        id="001",
        title="Test task",
        status="pending",
        priority="M",
        description="This is a test task.",
    )

    markdown = task.to_markdown()

    assert "---" in markdown
    assert "id: '001'" in markdown or "id: 001" in markdown
    assert "title: Test task" in markdown
    assert "status: pending" in markdown
    assert "priority: M" in markdown
    assert "This is a test task." in markdown


def test_task_from_markdown():
    """Test parsing task from markdown."""
    markdown = """---
id: '001'
title: Test task
status: pending
priority: H
project: test-project
assignees:
- '@user1'
- '@user2'
tags:
- bug
created: '2025-01-01T10:00:00'
modified: '2025-01-01T10:00:00'
---

This is a test task description.
"""

    task = Task.from_markdown(markdown, "001")

    assert task.id == "001"
    assert task.title == "Test task"
    assert task.status == "pending"
    assert task.priority == "H"
    assert task.project == "test-project"
    assert task.assignees == ["@user1", "@user2"]
    assert task.tags == ["bug"]
    assert "This is a test task description." in task.description


def test_task_save_and_load():
    """Test saving and loading tasks."""
    with TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)

        # Create task
        task = Task(
            id="001",
            title="Test task",
            status="pending",
            priority="M",
            description="Test description",
        )

        # Save task
        task_file = task.save(base_path)
        assert task_file.exists()
        assert task_file.name == "task-001.md"

        # Load task
        loaded_task = Task.load(task_file)
        assert loaded_task.id == "001"
        assert loaded_task.title == "Test task"
        assert loaded_task.status == "pending"
        assert loaded_task.priority == "M"
        assert loaded_task.description == "Test description"


def test_task_str():
    """Test string representation of task."""
    task = Task(
        id="001",
        title="Test task",
        status="pending",
        priority="H",
        project="my-project",
        assignees=["@user1"],
    )

    str_repr = str(task)
    assert "[001]" in str_repr
    assert "Test task" in str_repr
    assert "[my-project]" in str_repr
    assert "@user1" in str_repr
    assert "(pending, H)" in str_repr


def test_task_with_valid_links():
    """Test creating task with valid HTTP/HTTPS links."""
    task = Task(
        id="001",
        title="Test task",
        status="pending",
        priority="M",
        links=[
            "https://github.com/org/repo/issues/123",
            "http://example.com/doc",
            "https://mail.google.com/mail/u/0/#inbox/abc123",
        ],
    )

    assert len(task.links) == 3
    assert task.links[0] == "https://github.com/org/repo/issues/123"
    assert task.links[1] == "http://example.com/doc"
    assert task.links[2] == "https://mail.google.com/mail/u/0/#inbox/abc123"


def test_task_with_invalid_link():
    """Test that invalid URLs raise ValueError."""
    with pytest.raises(ValueError, match="Invalid URL"):
        Task(
            id="001",
            title="Test task",
            status="pending",
            priority="M",
            links=["not-a-url"],
        )

    with pytest.raises(ValueError, match="Invalid URL"):
        Task(
            id="001",
            title="Test task",
            status="pending",
            priority="M",
            links=["ftp://example.com"],  # Only HTTP/HTTPS allowed
        )


def test_task_links_to_markdown():
    """Test that links are serialized to markdown correctly."""
    task = Task(
        id="001",
        title="Test task",
        status="pending",
        priority="M",
        links=["https://github.com/org/repo/issues/123", "https://example.com"],
    )

    markdown = task.to_markdown()

    assert "links:" in markdown
    assert "https://github.com/org/repo/issues/123" in markdown
    assert "https://example.com" in markdown


def test_task_links_from_markdown():
    """Test parsing links from markdown."""
    markdown = """---
id: '001'
title: Test task
status: pending
priority: M
links:
- https://github.com/org/repo/issues/123
- https://example.com/doc
created: '2025-01-01T10:00:00'
modified: '2025-01-01T10:00:00'
---

Task description here.
"""

    task = Task.from_markdown(markdown, "001")

    assert len(task.links) == 2
    assert task.links[0] == "https://github.com/org/repo/issues/123"
    assert task.links[1] == "https://example.com/doc"


def test_task_links_backward_compatibility():
    """Test that tasks without links field can still be parsed."""
    markdown = """---
id: '001'
title: Test task
status: pending
priority: M
created: '2025-01-01T10:00:00'
modified: '2025-01-01T10:00:00'
---

Task without links field.
"""

    task = Task.from_markdown(markdown, "001")

    assert task.links == []


def test_task_validate_url():
    """Test URL validation helper method."""
    # Valid URLs
    assert Task.validate_url("https://github.com/org/repo") is True
    assert Task.validate_url("http://example.com") is True
    assert Task.validate_url("https://mail.google.com/mail/u/0/#inbox/abc") is True

    # Invalid URLs
    assert Task.validate_url("not-a-url") is False
    assert Task.validate_url("ftp://example.com") is False
    assert Task.validate_url("github.com") is False
    assert Task.validate_url("") is False
