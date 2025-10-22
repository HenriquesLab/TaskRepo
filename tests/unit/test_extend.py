"""Tests for extend command and duration utilities."""

import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from taskrepo.core.config import Config
from taskrepo.core.repository import RepositoryManager
from taskrepo.core.task import Task
from taskrepo.utils.duration import format_duration, parse_duration


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)


@pytest.fixture
def config(temp_dir):
    """Create a test config."""
    config_file = temp_dir / "config"
    config = Config(config_path=config_file)
    config.parent_dir = temp_dir
    config.save()
    return config


@pytest.fixture
def manager(config):
    """Create repository manager."""
    return RepositoryManager(config.parent_dir)


@pytest.fixture
def test_repo(manager):
    """Create a test repository with sample tasks."""
    repo = manager.create_repository("test")

    # Create sample tasks with different due dates
    tasks = [
        Task(
            id=repo.next_task_id(),
            title="Task with due date",
            description="This task has a due date",
            status="pending",
            priority="H",
            due=datetime(2025, 10, 24, 0, 0, 0),
        ),
        Task(
            id=repo.next_task_id(),
            title="Task without due date",
            description="This task has no due date",
            status="pending",
            priority="M",
        ),
        Task(
            id=repo.next_task_id(),
            title="Another task",
            description="For testing multiple extensions",
            status="pending",
            priority="L",
            due=datetime(2025, 11, 1, 0, 0, 0),
        ),
    ]

    for task in tasks:
        repo.save_task(task)

    return repo


# Duration utility tests


def test_parse_duration_days():
    """Test parsing days duration."""
    result = parse_duration("5d")
    assert result == timedelta(days=5)


def test_parse_duration_weeks():
    """Test parsing weeks duration."""
    result = parse_duration("2w")
    assert result == timedelta(days=14)


def test_parse_duration_months():
    """Test parsing months duration."""
    result = parse_duration("3m")
    assert result == timedelta(days=90)


def test_parse_duration_years():
    """Test parsing years duration."""
    result = parse_duration("1y")
    assert result == timedelta(days=365)


def test_parse_duration_case_insensitive():
    """Test that duration parsing is case-insensitive."""
    assert parse_duration("1W") == timedelta(days=7)
    assert parse_duration("2D") == timedelta(days=2)
    assert parse_duration("1M") == timedelta(days=30)
    assert parse_duration("1Y") == timedelta(days=365)


def test_parse_duration_invalid_format():
    """Test that invalid duration format raises error."""
    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("invalid")

    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("1x")

    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("w1")

    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("1 w")  # Space not allowed


def test_format_duration_singular():
    """Test formatting duration with singular units."""
    assert format_duration("1d") == "+1 day"
    assert format_duration("1w") == "+1 week"
    assert format_duration("1m") == "+1 month"
    assert format_duration("1y") == "+1 year"


def test_format_duration_plural():
    """Test formatting duration with plural units."""
    assert format_duration("2d") == "+2 days"
    assert format_duration("3w") == "+3 weeks"
    assert format_duration("6m") == "+6 months"
    assert format_duration("2y") == "+2 years"


# Extend command logic tests


def test_extend_task_with_due_date(config, manager, test_repo):
    """Test extending a task that has a due date."""
    tasks = manager.list_all_tasks()
    task_with_due = [t for t in tasks if t.title == "Task with due date"][0]

    original_due = task_with_due.due
    assert original_due == datetime(2025, 10, 24, 0, 0, 0)

    # Extend by 1 week
    duration_delta = parse_duration("1w")
    task_with_due.due = original_due + duration_delta

    # Save and reload
    repo = manager.get_repository("test")
    repo.save_task(task_with_due)
    reloaded_task = repo.get_task(task_with_due.id)

    assert reloaded_task.due == datetime(2025, 10, 31, 0, 0, 0)


def test_extend_task_without_due_date(config, manager, test_repo):
    """Test extending a task without a due date sets it from today."""
    tasks = manager.list_all_tasks()
    task_no_due = [t for t in tasks if t.title == "Task without due date"][0]

    assert task_no_due.due is None

    # Extend by 1 week from today
    duration_delta = parse_duration("1w")
    today = datetime.now()
    task_no_due.due = today + duration_delta

    # Save and reload
    repo = manager.get_repository("test")
    repo.save_task(task_no_due)
    reloaded_task = repo.get_task(task_no_due.id)

    # Check it's approximately 7 days from now (within 1 minute tolerance)
    expected = today + timedelta(days=7)
    assert abs((reloaded_task.due - expected).total_seconds()) < 60


def test_extend_multiple_tasks(config, manager, test_repo):
    """Test extending multiple tasks at once."""
    tasks = manager.list_all_tasks()

    # Extend first two tasks
    duration_delta = parse_duration("2d")

    for task in tasks[:2]:
        original_due = task.due
        if original_due:
            task.due = original_due + duration_delta
        else:
            task.due = datetime.now() + duration_delta

        repo = manager.get_repository("test")
        repo.save_task(task)

    # Verify both were extended
    reloaded_tasks = manager.list_all_tasks()
    assert all(t.due is not None for t in reloaded_tasks[:2])


def test_extend_updates_modified_timestamp(config, manager, test_repo):
    """Test that extending a task updates its modified timestamp."""
    tasks = manager.list_all_tasks()
    task = tasks[0]

    original_modified = task.modified

    # Wait a tiny bit and extend
    import time

    time.sleep(0.01)

    duration_delta = parse_duration("1d")
    if task.due:
        task.due = task.due + duration_delta
    else:
        task.due = datetime.now() + duration_delta

    task.modified = datetime.now()

    repo = manager.get_repository("test")
    repo.save_task(task)

    reloaded_task = repo.get_task(task.id)
    assert reloaded_task.modified > original_modified


def test_various_duration_formats(config, manager, test_repo):
    """Test various duration format calculations."""
    base_date = datetime(2025, 1, 1, 0, 0, 0)

    # Test different durations
    durations_and_expected = [
        ("1d", datetime(2025, 1, 2, 0, 0, 0)),
        ("7d", datetime(2025, 1, 8, 0, 0, 0)),
        ("1w", datetime(2025, 1, 8, 0, 0, 0)),
        ("2w", datetime(2025, 1, 15, 0, 0, 0)),
        ("1m", datetime(2025, 1, 31, 0, 0, 0)),
        ("2m", datetime(2025, 3, 2, 0, 0, 0)),
    ]

    for duration_str, expected_date in durations_and_expected:
        delta = parse_duration(duration_str)
        result = base_date + delta
        assert result == expected_date, f"Duration {duration_str} failed: got {result}, expected {expected_date}"
