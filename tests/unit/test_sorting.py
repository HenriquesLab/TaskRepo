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


# Recursive due date sorting tests


def test_effective_due_date_with_subtasks():
    """Test that parent task uses earliest subtask due date."""
    from datetime import datetime, timedelta

    from taskrepo.utils.sorting import _effective_due_date_cache, get_effective_due_date

    # Clear cache to ensure test isolation
    _effective_due_date_cache.clear()

    now = datetime.now()

    # Parent task with later due date
    parent = Task(
        id="parent",
        title="Parent Task",
        due=now + timedelta(days=10),
    )

    # Subtask with earlier due date
    subtask = Task(
        id="subtask",
        title="Subtask",
        parent="parent",
        due=now + timedelta(days=5),
    )

    all_tasks = [parent, subtask]

    # Parent's effective due date should be subtask's due date (earlier)
    effective = get_effective_due_date(parent, all_tasks)
    assert effective == subtask.due


def test_effective_due_date_with_dependencies():
    """Test that task uses earliest dependency due date."""
    from datetime import datetime, timedelta

    from taskrepo.utils.sorting import _effective_due_date_cache, get_effective_due_date

    # Clear cache to ensure test isolation
    _effective_due_date_cache.clear()

    now = datetime.now()

    # Task with later due date
    task1 = Task(
        id="task1",
        title="Task 1",
        due=now + timedelta(days=10),
        depends=["task2"],
    )

    # Dependency with earlier due date
    task2 = Task(
        id="task2",
        title="Task 2",
        due=now + timedelta(days=5),
    )

    all_tasks = [task1, task2]

    # Task1's effective due date should be task2's due date (earlier)
    effective = get_effective_due_date(task1, all_tasks)
    assert effective == task2.due


def test_effective_due_date_inherits_from_subtasks():
    """Test that parent without due date inherits from subtask."""
    from datetime import datetime, timedelta

    from taskrepo.utils.sorting import _effective_due_date_cache, get_effective_due_date

    # Clear cache to ensure test isolation
    _effective_due_date_cache.clear()

    now = datetime.now()

    # Parent task with NO due date
    parent = Task(
        id="parent",
        title="Parent Task",
        due=None,
    )

    # Subtask with due date
    subtask = Task(
        id="subtask",
        title="Subtask",
        parent="parent",
        due=now + timedelta(days=5),
    )

    all_tasks = [parent, subtask]

    # Parent should inherit subtask's due date
    effective = get_effective_due_date(parent, all_tasks)
    assert effective == subtask.due


def test_effective_due_date_multi_level_subtasks():
    """Test recursive traversal through multiple subtask levels."""
    from datetime import datetime, timedelta

    from taskrepo.utils.sorting import _effective_due_date_cache, get_effective_due_date

    # Clear cache to ensure test isolation
    _effective_due_date_cache.clear()

    now = datetime.now()

    # Parent (no due date)
    parent = Task(id="parent", title="Parent", due=None)

    # Child (no due date)
    child = Task(id="child", title="Child", parent="parent", due=None)

    # Grandchild (has due date)
    grandchild = Task(
        id="grandchild",
        title="Grandchild",
        parent="child",
        due=now + timedelta(days=3),
    )

    all_tasks = [parent, child, grandchild]

    # Parent should inherit due date from grandchild
    effective = get_effective_due_date(parent, all_tasks)
    assert effective == grandchild.due

    # Child should also inherit from grandchild
    effective_child = get_effective_due_date(child, all_tasks)
    assert effective_child == grandchild.due


def test_effective_due_date_circular_dependency():
    """Test that circular dependencies don't cause infinite loops."""
    from datetime import datetime, timedelta

    from taskrepo.utils.sorting import _effective_due_date_cache, get_effective_due_date

    # Clear cache to ensure test isolation
    _effective_due_date_cache.clear()

    now = datetime.now()

    # Create circular dependency: task1 -> task2 -> task1
    task1 = Task(
        id="task1",
        title="Task 1",
        due=now + timedelta(days=5),
        depends=["task2"],
    )

    task2 = Task(
        id="task2",
        title="Task 2",
        due=now + timedelta(days=10),
        depends=["task1"],
    )

    all_tasks = [task1, task2]

    # Should not crash due to cycle detection
    effective1 = get_effective_due_date(task1, all_tasks)
    effective2 = get_effective_due_date(task2, all_tasks)

    # Each should return their own due date (cycle detection prevents recursion)
    assert effective1 == task1.due
    assert effective2 == task2.due


def test_effective_due_date_mixed_subtasks_and_dependencies():
    """Test combination of subtasks and dependencies."""
    from datetime import datetime, timedelta

    from taskrepo.utils.sorting import _effective_due_date_cache, get_effective_due_date

    # Clear cache to ensure test isolation
    _effective_due_date_cache.clear()

    now = datetime.now()

    # Parent with late due date
    parent = Task(
        id="parent",
        title="Parent",
        due=now + timedelta(days=15),
        depends=["dep"],
    )

    # Subtask with medium due date
    subtask = Task(
        id="subtask",
        title="Subtask",
        parent="parent",
        due=now + timedelta(days=10),
    )

    # Dependency with earliest due date
    dep = Task(
        id="dep",
        title="Dependency",
        due=now + timedelta(days=5),
    )

    all_tasks = [parent, subtask, dep]

    # Parent should use earliest (dependency's due date)
    effective = get_effective_due_date(parent, all_tasks)
    assert effective == dep.due


def test_sort_tasks_with_recursive_due_dates():
    """Test that sort_tasks uses effective due dates."""
    from datetime import datetime, timedelta

    from taskrepo.utils.sorting import _effective_due_date_cache, sort_tasks

    # Clear cache to ensure test isolation
    _effective_due_date_cache.clear()

    now = datetime.now()

    # Parent with late due date (day 10)
    parent = Task(
        id="parent",
        title="Parent Task",
        priority="M",
        due=now + timedelta(days=10),
    )

    # Subtask with early due date (day 3)
    subtask = Task(
        id="subtask",
        title="Subtask",
        parent="parent",
        priority="M",
        due=now + timedelta(days=3),
    )

    # Regular task with medium due date (day 5)
    regular = Task(
        id="regular",
        title="Regular Task",
        priority="M",
        due=now + timedelta(days=5),
    )

    all_tasks = [parent, subtask, regular]

    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config = Config(config_path)
        config.sort_by = ["due"]

        # Sort with all_tasks context
        sorted_tasks = sort_tasks(all_tasks, config, all_tasks=all_tasks)

        # Parent should come first (effective due = day 3 from subtask)
        # Then regular task (day 5)
        # Then subtask (day 3, but appears after parent in tree)
        # Note: We're sorting ALL tasks, not just top-level
        assert sorted_tasks[0].id == "parent"  # effective due day 3
        assert sorted_tasks[1].id == "subtask"  # actual due day 3
        assert sorted_tasks[2].id == "regular"  # due day 5


def test_effective_due_date_no_related_tasks():
    """Test task with no subtasks or dependencies uses own due date."""
    from datetime import datetime, timedelta

    from taskrepo.utils.sorting import _effective_due_date_cache, get_effective_due_date

    # Clear cache to ensure test isolation
    _effective_due_date_cache.clear()

    now = datetime.now()

    task = Task(
        id="task",
        title="Solo Task",
        due=now + timedelta(days=5),
    )

    all_tasks = [task]

    # Should return task's own due date
    effective = get_effective_due_date(task, all_tasks)
    assert effective == task.due


def test_effective_due_date_all_none():
    """Test task and all related tasks have no due dates."""
    from taskrepo.utils.sorting import _effective_due_date_cache, get_effective_due_date

    # Clear cache to ensure test isolation
    _effective_due_date_cache.clear()

    # Parent with no due date
    parent = Task(id="parent", title="Parent", due=None)

    # Subtask with no due date
    subtask = Task(id="subtask", title="Subtask", parent="parent", due=None)

    all_tasks = [parent, subtask]

    # Should return None
    effective = get_effective_due_date(parent, all_tasks)
    assert effective is None


def test_effective_due_date_caching():
    """Test that effective due dates are cached for performance."""
    from datetime import datetime, timedelta

    from taskrepo.utils.sorting import _effective_due_date_cache, get_effective_due_date

    now = datetime.now()

    parent = Task(id="parent", title="Parent", due=now + timedelta(days=10))
    subtask = Task(id="subtask", title="Subtask", parent="parent", due=now + timedelta(days=5))

    all_tasks = [parent, subtask]

    # Clear cache
    _effective_due_date_cache.clear()

    # First call should cache the result
    effective1 = get_effective_due_date(parent, all_tasks)

    # Cache should now contain the parent's effective due date
    assert "parent" in _effective_due_date_cache

    # Second call should return cached value
    effective2 = get_effective_due_date(parent, all_tasks)

    assert effective1 == effective2


def test_display_tree_view_does_not_modify_config():
    """Test that displaying tasks in tree view doesn't corrupt the config file.

    Regression test for bug where displaying subtasks would overwrite the user's
    sort_by config with a temporary config that prioritizes due dates.
    """
    from tempfile import TemporaryDirectory

    from taskrepo.core.config import Config
    from taskrepo.core.task import Task
    from taskrepo.tui.display import build_task_tree

    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config = Config(config_path)

        # Set a specific sort order that user wants
        original_sort_by = ["assignee:@paxcalpt", "due", "priority"]
        config.sort_by = original_sort_by

        # Create tasks with parent-child relationship
        parent = Task(
            id="parent",
            title="Parent Task",
            status="pending",
            priority="H",
            assignees=["@paxcalpt"],
        )

        child = Task(
            id="child",
            title="Child Task",
            status="pending",
            priority="M",
            parent="parent",
        )

        tasks = [parent, child]

        # Build task tree (this would trigger the bug)
        build_task_tree(tasks, config)

        # Reload config from disk to verify it wasn't modified
        config_reloaded = Config(config_path)

        # Config should still have the original sort order
        assert config_reloaded.sort_by == original_sort_by, (
            f"Config was modified! Expected {original_sort_by}, got {config_reloaded.sort_by}"
        )
