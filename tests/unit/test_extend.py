"""Tests for extend command and duration utilities."""

import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from taskrepo.core.config import Config
from taskrepo.core.repository import RepositoryManager
from taskrepo.core.task import Task
from taskrepo.utils.date_parser import parse_date_or_duration
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


# Date parser tests (weekday references)


def test_parse_next_monday():
    """Test parsing 'next monday'."""
    # Test from Wednesday (2025-11-05)
    today = datetime(2025, 11, 5)  # Wednesday
    from taskrepo.utils.date_parser import _parse_weekday_reference

    result = _parse_weekday_reference("next monday", today)
    # Should be Monday of next week (Nov 10)
    assert result == datetime(2025, 11, 10)


def test_parse_this_friday():
    """Test parsing 'this friday'."""
    # Test from Wednesday (2025-11-05)
    today = datetime(2025, 11, 5)  # Wednesday
    from taskrepo.utils.date_parser import _parse_weekday_reference

    result = _parse_weekday_reference("this friday", today)
    # Should be Friday of this week (Nov 7)
    assert result == datetime(2025, 11, 7)


def test_parse_just_monday():
    """Test parsing just 'monday'."""
    # Test from Wednesday (2025-11-05)
    today = datetime(2025, 11, 5)  # Wednesday
    from taskrepo.utils.date_parser import _parse_weekday_reference

    result = _parse_weekday_reference("monday", today)
    # Should be next Monday (Nov 10)
    assert result == datetime(2025, 11, 10)


def test_parse_same_weekday():
    """Test parsing a weekday when today is that weekday."""
    # Test from Monday (2025-11-03)
    today = datetime(2025, 11, 3)  # Monday
    from taskrepo.utils.date_parser import _parse_weekday_reference

    # Just "monday" should give next Monday (7 days ahead)
    result = _parse_weekday_reference("monday", today)
    assert result == datetime(2025, 11, 10)

    # "next monday" should also give next Monday (7 days ahead)
    result = _parse_weekday_reference("next monday", today)
    assert result == datetime(2025, 11, 10)


def test_parse_all_weekdays():
    """Test parsing all weekday names."""
    today = datetime(2025, 11, 5)  # Wednesday
    from taskrepo.utils.date_parser import _parse_weekday_reference

    expected_dates = {
        "monday": datetime(2025, 11, 10),  # Next Monday
        "tuesday": datetime(2025, 11, 11),  # Next Tuesday
        "wednesday": datetime(2025, 11, 12),  # Next Wednesday (7 days ahead)
        "thursday": datetime(2025, 11, 6),  # This Thursday
        "friday": datetime(2025, 11, 7),  # This Friday
        "saturday": datetime(2025, 11, 8),  # This Saturday
        "sunday": datetime(2025, 11, 9),  # This Sunday
    }

    for weekday, expected in expected_dates.items():
        result = _parse_weekday_reference(weekday, today)
        assert result == expected, f"Weekday {weekday} failed: got {result}, expected {expected}"


def test_parse_invalid_weekday_reference():
    """Test that invalid weekday references return None."""
    today = datetime(2025, 11, 5)
    from taskrepo.utils.date_parser import _parse_weekday_reference

    # Invalid patterns
    assert _parse_weekday_reference("invalid", today) is None
    assert _parse_weekday_reference("next week monday", today) is None
    assert _parse_weekday_reference("monday next", today) is None
    assert _parse_weekday_reference("prev monday", today) is None


def test_date_or_duration_parser_weekdays():
    """Test the main parse_date_or_duration function with weekday references."""
    # Mock today as Wednesday (2025-11-05)
    import unittest.mock

    with unittest.mock.patch("taskrepo.utils.date_parser.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 11, 5, 12, 30, 0)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        # Test "next monday"
        result, is_absolute = parse_date_or_duration("next monday")
        assert is_absolute is True
        assert result == datetime(2025, 11, 10)

        # Test "this friday"
        result, is_absolute = parse_date_or_duration("this friday")
        assert is_absolute is True
        assert result == datetime(2025, 11, 7)

        # Test just "monday"
        result, is_absolute = parse_date_or_duration("monday")
        assert is_absolute is True
        assert result == datetime(2025, 11, 10)


def test_date_or_duration_parser_case_insensitive():
    """Test that weekday parsing is case-insensitive."""
    import unittest.mock

    with unittest.mock.patch("taskrepo.utils.date_parser.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 11, 5, 12, 30, 0)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        # Different case variations
        result1, _ = parse_date_or_duration("Next Monday")
        result2, _ = parse_date_or_duration("next MONDAY")
        result3, _ = parse_date_or_duration("NEXT MONDAY")

        # All should give same result
        assert result1 == result2 == result3 == datetime(2025, 11, 10)
