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
