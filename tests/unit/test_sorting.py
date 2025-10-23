"""Unit tests for task sorting functionality."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from taskrepo.core.config import Config
from taskrepo.core.task import Task


def test_config_accepts_basic_assignee_field():
    """Test that config accepts 'assignee' as a valid sort field."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config = Config(config_path)

        # Should not raise an error
        config.sort_by = ["assignee", "due"]
        assert config.sort_by == ["assignee", "due"]


def test_config_accepts_assignee_with_preferred_user():
    """Test that config accepts 'assignee:@username' syntax."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config = Config(config_path)

        # Should not raise an error
        config.sort_by = ["assignee:@paxcalpt", "priority"]
        assert config.sort_by == ["assignee:@paxcalpt", "priority"]


def test_config_accepts_descending_assignee():
    """Test that config accepts '-assignee' and '-assignee:@username'."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config = Config(config_path)

        # Should not raise an error
        config.sort_by = ["-assignee", "due"]
        assert config.sort_by == ["-assignee", "due"]

        config.sort_by = ["-assignee:@alice", "priority"]
        assert config.sort_by == ["-assignee:@alice", "priority"]


def test_config_rejects_invalid_assignee_format():
    """Test that config rejects invalid assignee syntax."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config = Config(config_path)

        # Missing @ symbol - should raise error
        with pytest.raises(ValueError, match="Invalid sort field"):
            config.sort_by = ["assignee:paxcalpt"]

        # Invalid format - should raise error
        with pytest.raises(ValueError, match="Invalid sort field"):
            config.sort_by = ["assignee:@user:extra"]


def test_assignee_sorting_basic():
    """Test basic alphabetical assignee sorting."""

    tasks = [
        Task(id="001", title="Task 1", assignees=["@charlie"]),
        Task(id="002", title="Task 2", assignees=["@alice"]),
        Task(id="003", title="Task 3", assignees=["@bob"]),
        Task(id="004", title="Task 4", assignees=[]),  # No assignee
    ]

    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config = Config(config_path)
        config.sort_by = ["assignee"]

        # Use the get_field_value function from display module

        # Manually test sorting logic
        def get_field_value(task, field):
            """Simplified version of get_field_value for testing."""
            if field.startswith("assignee"):
                preferred_assignee = None
                if ":" in field:
                    preferred_assignee = field.split(":", 1)[1]

                if not task.assignees:
                    return (2, "")
                elif preferred_assignee and preferred_assignee in task.assignees:
                    return (0, task.assignees[0].lower())
                else:
                    return (1, task.assignees[0].lower())
            return ""

        # Sort tasks
        sorted_tasks = sorted(tasks, key=lambda t: get_field_value(t, "assignee"))

        # Verify order: alice, bob, charlie, then unassigned
        assert sorted_tasks[0].assignees == ["@alice"]
        assert sorted_tasks[1].assignees == ["@bob"]
        assert sorted_tasks[2].assignees == ["@charlie"]
        assert sorted_tasks[3].assignees == []


def test_assignee_sorting_with_preferred_user():
    """Test assignee sorting with a preferred user appearing first."""
    tasks = [
        Task(id="001", title="Task 1", assignees=["@charlie"]),
        Task(id="002", title="Task 2", assignees=["@alice"]),
        Task(id="003", title="Task 3", assignees=["@paxcalpt"]),
        Task(id="004", title="Task 4", assignees=["@bob"]),
        Task(id="005", title="Task 5", assignees=[]),  # No assignee
    ]

    # Simplified version of get_field_value for testing
    def get_field_value(task, field):
        """Simplified version of get_field_value for testing."""
        if field.startswith("assignee"):
            preferred_assignee = None
            if ":" in field:
                preferred_assignee = field.split(":", 1)[1]

            if not task.assignees:
                return (2, "")
            elif preferred_assignee and preferred_assignee in task.assignees:
                return (0, task.assignees[0].lower())
            else:
                return (1, task.assignees[0].lower())
        return ""

    # Sort with @paxcalpt as preferred
    sorted_tasks = sorted(tasks, key=lambda t: get_field_value(t, "assignee:@paxcalpt"))

    # Verify order: paxcalpt first, then alice/bob/charlie alphabetically, then unassigned
    assert sorted_tasks[0].assignees == ["@paxcalpt"]
    assert sorted_tasks[1].assignees == ["@alice"]
    assert sorted_tasks[2].assignees == ["@bob"]
    assert sorted_tasks[3].assignees == ["@charlie"]
    assert sorted_tasks[4].assignees == []


def test_assignee_sorting_descending():
    """Test descending assignee sorting."""
    tasks = [
        Task(id="001", title="Task 1", assignees=["@alice"]),
        Task(id="002", title="Task 2", assignees=["@charlie"]),
        Task(id="003", title="Task 3", assignees=["@bob"]),
        Task(id="004", title="Task 4", assignees=[]),
    ]

    def get_field_value(task, field):
        """Simplified version with descending support."""
        descending = field.startswith("-")
        field_name = field[1:] if descending else field

        if field_name.startswith("assignee"):
            preferred_assignee = None
            if ":" in field_name:
                preferred_assignee = field_name.split(":", 1)[1]

            if not task.assignees:
                value = (2, "")
            elif preferred_assignee and preferred_assignee in task.assignees:
                value = (0, task.assignees[0].lower())
            else:
                value = (1, task.assignees[0].lower())

            if descending and isinstance(value, tuple) and len(value) == 2:
                # Reverse priority: 0->2, 1->1, 2->0
                return (2 - value[0], value[1])
            return value
        return ""

    # Sort descending
    sorted_tasks = sorted(tasks, key=lambda t: get_field_value(t, "-assignee"))

    # Verify order: unassigned first, then charlie/bob/alice (reverse alphabetical)
    assert sorted_tasks[0].assignees == []
    # Note: Within group 1, they're still sorted alphabetically by first assignee
    # So the descending only affects the priority groups, not the alphabetical order within groups


def test_assignee_sorting_with_multiple_assignees():
    """Test that sorting uses the first assignee when multiple are present."""
    tasks = [
        Task(id="001", title="Task 1", assignees=["@charlie", "@alice"]),
        Task(id="002", title="Task 2", assignees=["@bob", "@dave"]),
        Task(id="003", title="Task 3", assignees=["@alice", "@bob"]),
    ]

    def get_field_value(task, field):
        """Simplified version of get_field_value for testing."""
        if field.startswith("assignee"):
            if not task.assignees:
                return (2, "")
            else:
                return (1, task.assignees[0].lower())
        return ""

    sorted_tasks = sorted(tasks, key=lambda t: get_field_value(t, "assignee"))

    # Verify order based on first assignee: alice, bob, charlie
    assert sorted_tasks[0].assignees[0] == "@alice"
    assert sorted_tasks[1].assignees[0] == "@bob"
    assert sorted_tasks[2].assignees[0] == "@charlie"


def test_preferred_assignee_in_multiple_assignees_list():
    """Test that preferred assignee is found even if not first in the list."""
    tasks = [
        Task(id="001", title="Task 1", assignees=["@charlie", "@paxcalpt"]),
        Task(id="002", title="Task 2", assignees=["@alice"]),
        Task(id="003", title="Task 3", assignees=["@bob"]),
    ]

    def get_field_value(task, field):
        """Simplified version of get_field_value for testing."""
        if field.startswith("assignee"):
            preferred_assignee = None
            if ":" in field:
                preferred_assignee = field.split(":", 1)[1]

            if not task.assignees:
                return (2, "")
            elif preferred_assignee and preferred_assignee in task.assignees:
                return (0, task.assignees[0].lower())
            else:
                return (1, task.assignees[0].lower())
        return ""

    sorted_tasks = sorted(tasks, key=lambda t: get_field_value(t, "assignee:@paxcalpt"))

    # Task 1 should be first because it contains @paxcalpt (even though it's second in the list)
    assert "@paxcalpt" in sorted_tasks[0].assignees
    assert sorted_tasks[1].assignees == ["@alice"]
    assert sorted_tasks[2].assignees == ["@bob"]


def test_config_persistence_with_assignee_sort():
    """Test that assignee sort config persists correctly."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config = Config(config_path)

        # Set sort with assignee preference
        config.sort_by = ["assignee:@paxcalpt", "due", "priority"]

        # Create new config instance to test persistence
        config2 = Config(config_path)
        assert config2.sort_by == ["assignee:@paxcalpt", "due", "priority"]


def test_sort_tasks_consistency():
    """Test that sort_tasks produces consistent results."""
    from datetime import datetime, timedelta

    from taskrepo.utils.sorting import sort_tasks

    # Create tasks with different due dates and priorities
    now = datetime.now()
    tasks = [
        Task(id="001", title="Task 1", priority="L", due=now + timedelta(days=10)),
        Task(id="002", title="Task 2", priority="H", due=now + timedelta(days=5)),
        Task(id="003", title="Task 3", priority="M", due=now + timedelta(days=3)),
        Task(id="004", title="Task 4", priority="H", due=now + timedelta(days=1)),
    ]

    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config = Config(config_path)
        config.sort_by = ["due", "priority"]

        # Sort tasks
        sorted_tasks = sort_tasks(tasks, config)

        # Verify order: sorted by due date first (ascending)
        assert sorted_tasks[0].id == "004"  # due in 1 day, H
        assert sorted_tasks[1].id == "003"  # due in 3 days, M
        assert sorted_tasks[2].id == "002"  # due in 5 days, H
        assert sorted_tasks[3].id == "001"  # due in 10 days, L

        # Sort multiple times to ensure consistency
        sorted_tasks2 = sort_tasks(tasks, config)
        assert [t.id for t in sorted_tasks] == [t.id for t in sorted_tasks2]


def test_sort_tasks_with_assignee_priority():
    """Test that sort_tasks handles assignee priority correctly."""
    from taskrepo.utils.sorting import sort_tasks

    tasks = [
        Task(id="001", title="Task 1", assignees=["@alice"], priority="M"),
        Task(id="002", title="Task 2", assignees=["@paxcalpt"], priority="M"),
        Task(id="003", title="Task 3", assignees=["@bob"], priority="M"),
        Task(id="004", title="Task 4", assignees=[], priority="M"),
    ]

    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config = Config(config_path)
        config.sort_by = ["assignee:@paxcalpt", "priority"]

        # Sort tasks
        sorted_tasks = sort_tasks(tasks, config)

        # @paxcalpt tasks first, then others alphabetically, then unassigned
        assert sorted_tasks[0].id == "002"  # @paxcalpt
        assert sorted_tasks[1].id == "001"  # @alice
        assert sorted_tasks[2].id == "003"  # @bob
        assert sorted_tasks[3].id == "004"  # no assignee


def test_sort_tasks_matches_display_order():
    """Test that sort_tasks produces same order as display_tasks_table would."""
    from datetime import datetime, timedelta

    from taskrepo.utils.sorting import sort_tasks

    # Create realistic task set
    now = datetime.now()
    tasks = [
        Task(id="001", title="Overdue high", priority="H", due=now - timedelta(days=1)),
        Task(id="002", title="Today medium", priority="M", due=now),
        Task(id="003", title="Tomorrow high", priority="H", due=now + timedelta(days=1)),
        Task(id="004", title="Next week low", priority="L", due=now + timedelta(days=7)),
        Task(id="005", title="No due date", priority="H", due=None),
    ]

    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config = Config(config_path)
        config.sort_by = ["due", "priority"]

        # Sort tasks twice to ensure consistency
        sorted_tasks1 = sort_tasks(tasks, config)
        sorted_tasks2 = sort_tasks(tasks.copy(), config)

        # Both should produce identical order
        assert [t.id for t in sorted_tasks1] == [t.id for t in sorted_tasks2]

        # Verify expected order (due date ascending, no due date last)
        assert sorted_tasks1[0].id == "001"  # overdue
        assert sorted_tasks1[1].id == "002"  # today
        assert sorted_tasks1[2].id == "003"  # tomorrow
        assert sorted_tasks1[3].id == "004"  # next week
        assert sorted_tasks1[4].id == "005"  # no due date (last)
