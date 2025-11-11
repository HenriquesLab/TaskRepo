"""Tests for urgency-based task sorting."""

from datetime import datetime, timedelta

from taskrepo.core.config import Config
from taskrepo.core.task import Task
from taskrepo.utils.sorting import sort_tasks


def test_urgency_sort_overdue_first():
    """Test that overdue tasks appear before today's tasks."""
    now = datetime.now()

    task_overdue = Task(
        id="overdue",
        title="Overdue task",
        status="pending",
        priority="M",
        due=now - timedelta(days=3),  # 3 days ago
    )

    task_today = Task(
        id="today",
        title="Today task",
        status="pending",
        priority="M",
        due=now,  # Today
    )

    tasks = [task_today, task_overdue]

    # Create config with urgency sort
    config = Config()
    config._data["sort_by"] = ["urgency"]

    sorted_tasks = sort_tasks(tasks, config, all_tasks=tasks)

    # Overdue should come first
    assert sorted_tasks[0].id == "overdue"
    assert sorted_tasks[1].id == "today"


def test_urgency_sort_priority_secondary():
    """Test that priority is used as secondary sort within same urgency level."""
    now = datetime.now()

    task_overdue_h = Task(
        id="overdue_h",
        title="Overdue High",
        status="pending",
        priority="H",
        due=now - timedelta(days=3),
    )

    task_overdue_l = Task(
        id="overdue_l",
        title="Overdue Low",
        status="pending",
        priority="L",
        due=now - timedelta(days=5),
    )

    tasks = [task_overdue_l, task_overdue_h]

    # Create config with urgency + priority sort
    config = Config()
    config._data["sort_by"] = ["urgency", "priority"]

    sorted_tasks = sort_tasks(tasks, config, all_tasks=tasks)

    # Both overdue, but H priority comes first
    assert sorted_tasks[0].id == "overdue_h"
    assert sorted_tasks[1].id == "overdue_l"


def test_urgency_sort_order():
    """Test complete urgency order: overdue -> today -> soon -> future."""
    now = datetime.now()

    task_overdue = Task(
        id="overdue",
        title="Overdue",
        status="pending",
        priority="M",
        due=now - timedelta(days=1),
    )

    task_today = Task(
        id="today",
        title="Today",
        status="pending",
        priority="M",
        due=now,
    )

    task_soon = Task(
        id="soon",
        title="Soon",
        status="pending",
        priority="M",
        due=now + timedelta(days=3),  # Within 1 week
    )

    task_future = Task(
        id="future",
        title="Future",
        status="pending",
        priority="M",
        due=now + timedelta(days=60),  # 2 months
    )

    task_no_due = Task(
        id="no_due",
        title="No Due Date",
        status="pending",
        priority="M",
    )

    tasks = [task_no_due, task_future, task_soon, task_today, task_overdue]

    config = Config()
    config._data["sort_by"] = ["urgency"]

    sorted_tasks = sort_tasks(tasks, config, all_tasks=tasks)

    # Check order: overdue -> today -> soon -> future -> no_due
    assert sorted_tasks[0].id == "overdue"
    assert sorted_tasks[1].id == "today"
    assert sorted_tasks[2].id == "soon"
    assert sorted_tasks[3].id == "future"
    assert sorted_tasks[4].id == "no_due"


def test_urgency_vs_due_sorting():
    """Test that urgency sorting differs from due date sorting."""
    now = datetime.now()

    task_old_overdue = Task(
        id="old_overdue",
        title="Old Overdue",
        status="pending",
        priority="M",
        due=now - timedelta(days=10),  # Oldest date
    )

    task_recent_overdue = Task(
        id="recent_overdue",
        title="Recent Overdue",
        status="pending",
        priority="M",
        due=now - timedelta(days=1),
    )

    task_today = Task(
        id="today",
        title="Today",
        status="pending",
        priority="M",
        due=now,
    )

    tasks = [task_today, task_recent_overdue, task_old_overdue]

    # Sort by due date (chronological)
    config_due = Config()
    config_due._data["sort_by"] = ["due"]
    sorted_by_due = sort_tasks(tasks, config_due, all_tasks=tasks)

    # Sort by urgency
    config_urgency = Config()
    config_urgency._data["sort_by"] = ["urgency"]
    sorted_by_urgency = sort_tasks(tasks, config_urgency, all_tasks=tasks)

    # Due date sorting: oldest first (old_overdue -> recent_overdue -> today)
    assert sorted_by_due[0].id == "old_overdue"
    assert sorted_by_due[1].id == "recent_overdue"
    assert sorted_by_due[2].id == "today"

    # Urgency sorting: all overdue tasks at top (same urgency level), then today
    # Within overdue, priority is secondary sort (both M, so by due date)
    assert sorted_by_urgency[0].id == "old_overdue"  # Overdue
    assert sorted_by_urgency[1].id == "recent_overdue"  # Overdue
    assert sorted_by_urgency[2].id == "today"  # Today


def test_urgency_with_completed_tasks():
    """Test that completed tasks sort to bottom regardless of urgency."""
    now = datetime.now()

    task_overdue_pending = Task(
        id="overdue_pending",
        title="Overdue Pending",
        status="pending",
        priority="H",
        due=now - timedelta(days=3),
    )

    task_overdue_completed = Task(
        id="overdue_completed",
        title="Overdue Completed",
        status="completed",
        priority="H",
        due=now - timedelta(days=3),
    )

    tasks = [task_overdue_completed, task_overdue_pending]

    config = Config()
    config._data["sort_by"] = ["urgency"]

    sorted_tasks = sort_tasks(tasks, config, all_tasks=tasks)

    # Pending task comes first, completed goes to bottom
    assert sorted_tasks[0].id == "overdue_pending"
    assert sorted_tasks[1].id == "overdue_completed"
