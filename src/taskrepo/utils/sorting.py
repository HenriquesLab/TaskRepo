"""Sorting utilities for tasks.

⚠️ IMPORTANT: This module is the single source of truth for task sorting logic.
The following components depend on this module:
- CLI list command (cli/commands/list.py)
- TUI display (tui/display.py, tui/task_tui.py)
- README generation (core/repository.py: generate_readme, generate_archive_readme)
- Archive display (cli/commands/archive.py)
- Sync operations (cli/commands/sync.py)

When modifying sorting logic here, verify that README generation still works correctly.
README files should display tasks in the same order as 'tsk list' command.
"""

from datetime import datetime
from typing import Any, Optional

from taskrepo.core.config import Config
from taskrepo.core.task import Task

# Cache for effective due dates during a sort operation
# Format: {task_id: effective_due_date}
_effective_due_date_cache: dict[str, Optional[datetime]] = {}


def get_effective_due_date(
    task: Task,
    all_tasks: list[Task],
    visited: Optional[set[str]] = None,
) -> Optional[datetime]:
    """Get the earliest due date from a task, its subtasks, and dependencies.

    This function recursively traverses:
    1. All subtasks (tasks that have this task as parent)
    2. All dependencies (tasks referenced in the depends field)

    It finds the earliest due date among all related tasks. If the task itself
    has no due date but any subtask/dependency does, it inherits that earliest date.

    Args:
        task: The task to get effective due date for
        all_tasks: All tasks in the system (for lookup)
        visited: Set of task IDs already visited (for cycle detection)

    Returns:
        Earliest due date among task and all related tasks, or None if none have due dates

    Examples:
        >>> # Parent due 2025-11-15, subtask due 2025-11-10
        >>> get_effective_due_date(parent_task, all_tasks)
        datetime(2025, 11, 10)  # Returns earliest

        >>> # Parent has no due date, subtask due 2025-11-10
        >>> get_effective_due_date(parent_task, all_tasks)
        datetime(2025, 11, 10)  # Inherits from subtask
    """
    # Check cache first (for performance)
    if task.id in _effective_due_date_cache:
        return _effective_due_date_cache[task.id]

    # Initialize visited set for cycle detection
    if visited is None:
        visited = set()

    # Detect cycles - if we've seen this task before, skip it
    if task.id in visited:
        return None

    # Mark this task as visited
    visited.add(task.id)

    # Start with this task's due date
    earliest_due = task.due

    # Build a map of all tasks by ID for fast lookup
    task_map = {t.id: t for t in all_tasks}

    # Find all active subtasks (tasks where parent == this task's id)
    # Exclude completed/cancelled subtasks as their due dates shouldn't affect parent urgency
    subtasks = [t for t in all_tasks if t.parent == task.id and t.status not in ("completed", "cancelled")]

    # Find all active dependency tasks (tasks referenced in depends field)
    # Exclude completed/cancelled dependencies as they're no longer blocking
    dependency_tasks = []
    for dep_id in task.depends:
        dep_task = task_map.get(dep_id)
        if dep_task and dep_task.status not in ("completed", "cancelled"):
            dependency_tasks.append(dep_task)

    # Recursively get effective due dates for subtasks and dependencies
    related_tasks = subtasks + dependency_tasks

    for related_task in related_tasks:
        # Recursively get the effective due date for this related task
        related_due = get_effective_due_date(related_task, all_tasks, visited.copy())

        # Update earliest_due if this related task has an earlier date
        if related_due:
            if earliest_due is None or related_due < earliest_due:
                earliest_due = related_due

    # Cache the result
    _effective_due_date_cache[task.id] = earliest_due

    return earliest_due


def get_due_date_cluster(due_date: Optional[datetime]) -> int:
    """Convert due date to cluster bucket for sorting.

    Clusters tasks by week-based countdown buckets instead of exact timestamps.
    This allows grouping similar due dates together when sorting, so secondary
    sort fields (like priority) take precedence within each bucket.

    Args:
        due_date: Task due date

    Returns:
        Bucket number for clustering:
        Overdue (negative):
        -8: Overdue by 8+ weeks
        -7: Overdue by 7 weeks
        ... (one bucket per week)
        -1: Overdue by 1 week
         0: Overdue by 1-6 days

        Future (positive):
         1: Today
         2: 1-6 days
         3: 1 week (7-13 days)
         4: 2 weeks (14-20 days)
         5: 3 weeks (21-27 days)
         ... (one bucket per week)
         20: 18+ weeks (126+ days)
         99: No due date
    """
    if not due_date:
        return 99  # No due date - sort last

    now = datetime.now()
    diff = due_date - now
    days = diff.days

    # Overdue
    if days < 0:
        abs_days = abs(days)
        if abs_days < 7:
            return 0  # Overdue by 1-6 days
        else:
            # One bucket per week, capped at 8 weeks
            weeks = min(abs_days // 7, 8)
            return -weeks  # -1 to -8

    # Today
    if days == 0:
        return 1

    # Future: 1-6 days
    if days < 7:
        return 2  # 1-6 days

    # Future: weeks (one bucket per week, capped at 18 weeks)
    weeks = min(days // 7, 18)
    return 2 + weeks  # 3 (1w) through 20 (18w+)


def sort_tasks(tasks: list[Task], config: Config, all_tasks: Optional[list[Task]] = None) -> list[Task]:
    """Sort tasks according to configuration settings.

    When sorting by 'due' date, this function considers not just the task's own due date,
    but also the earliest due date from all its subtasks and dependencies. This ensures
    that parent tasks with urgent subtasks appear higher in the list.

    Args:
        tasks: List of tasks to sort
        config: Configuration object containing sort_by settings
        all_tasks: All tasks in the system (for calculating effective due dates).
                   If not provided, defaults to tasks (no cross-task context).

    Returns:
        Sorted list of tasks
    """
    # Clear the effective due date cache for this sort operation
    global _effective_due_date_cache
    _effective_due_date_cache.clear()

    # If all_tasks not provided, use tasks (for backward compatibility)
    if all_tasks is None:
        all_tasks = tasks

    def get_field_value(task: Task, field: str) -> tuple[bool, Any]:
        """Get sortable value for a field.

        Args:
            task: Task to get value from
            field: Field name (may have '-' prefix for descending)

        Returns:
            Tuple of (is_descending, value)
        """
        # Handle descending order prefix
        descending = field.startswith("-")
        field_name = field[1:] if descending else field

        if field_name == "priority":
            priority_order = {"H": 0, "M": 1, "L": 2}
            value = priority_order.get(task.priority, 3)
        elif field_name == "due":
            # Completed/cancelled tasks should sort to bottom (treat as no due date)
            if task.status in ("completed", "cancelled"):
                value = float("inf") if not config.cluster_due_dates else 99
            else:
                # Get effective due date (considering subtasks and dependencies)
                effective_due = get_effective_due_date(task, all_tasks)

                if config.cluster_due_dates:
                    # Use cluster bucket instead of exact timestamp
                    value = get_due_date_cluster(effective_due)
                else:
                    # Use exact timestamp
                    value = effective_due.timestamp() if effective_due else float("inf")
        elif field_name == "urgency":
            # Sort by urgency level (overdue first, then today, then future)
            # Completed/cancelled tasks should sort to bottom
            if task.status in ("completed", "cancelled"):
                value = 999
            else:
                # Get effective due date (considering subtasks and dependencies)
                effective_due = get_effective_due_date(task, all_tasks)

                if effective_due is None:
                    # No due date - least urgent
                    value = 100
                else:
                    from taskrepo.utils.countdown import calculate_countdown

                    _, status, urgency_level = calculate_countdown(effective_due)

                    # Map urgency to sort order (lower = more urgent, sorts first)
                    urgency_order = {
                        "critical": 0,  # Overdue or now
                        "high": 1,  # Today
                        "medium": 2,  # Soon (1 week)
                        "low": 3,  # Future
                    }
                    value = urgency_order.get(urgency_level, 4)
        elif field_name == "created":
            value = task.created.timestamp()
        elif field_name == "modified":
            value = task.modified.timestamp()
        elif field_name == "status":
            status_order = {"pending": 0, "in-progress": 1, "completed": 2, "cancelled": 3}
            value = status_order.get(task.status, 4)
        elif field_name == "title":
            value = task.title.lower()
        elif field_name == "project":
            value = (task.project or "").lower()
        elif field_name.startswith("assignee"):
            # Handle assignee sorting with optional preferred user
            # Format: "assignee" or "assignee:@username"
            preferred_assignee = None
            if ":" in field_name:
                # Extract preferred assignee (e.g., "assignee:@paxcalpt" -> "@paxcalpt")
                preferred_assignee = field_name.split(":", 1)[1]

            if not task.assignees:
                # No assignees - sort last
                value = (2, "")
            elif preferred_assignee and preferred_assignee in task.assignees:
                # Task has the preferred assignee - sort first
                # Use preferred assignee for secondary sort to treat all matching tasks equally
                value = (0, preferred_assignee.lower())
            else:
                # Task has assignees but not the preferred one (or no preference)
                first_assignee = task.assignees[0].lower()
                value = (1, first_assignee)
        else:
            value = ""

        # Reverse for descending order
        if descending:
            if isinstance(value, (int, float)):
                value = -value if value != float("inf") else float("-inf")
            elif isinstance(value, str):
                # For strings, we'll reverse the sort later
                return (True, value)  # Flag as descending
            elif isinstance(value, tuple):
                # For tuple values (like assignee), reverse the priority order
                if len(value) == 2 and isinstance(value[0], int):
                    # Reverse priority group: 0->2, 1->1, 2->0
                    return (True, (2 - value[0], value[1]))

        return (False, value) if not descending else (True, value)

    def get_sort_key(task: Task) -> tuple:
        """Get sort key for a task.

        Args:
            task: Task to get sort key for

        Returns:
            Tuple of values to sort by
        """
        sort_fields = config.sort_by
        key_parts = []
        due_field_info = None  # Track due field for timestamp tiebreaker

        for field in sort_fields:
            is_desc, value = get_field_value(task, field)
            key_parts.append(value)

            # When clustering is enabled and this is the 'due' field,
            # remember it for adding timestamp tiebreaker at the end
            if config.cluster_due_dates and field.lstrip("-") == "due":
                # Use effective due date for tiebreaker as well
                effective_due = get_effective_due_date(task, all_tasks)
                due_field_info = (field, effective_due)

        # Add exact timestamp as final tiebreaker when clustering is enabled
        # This ensures all configured sort fields take precedence within same bucket
        if due_field_info:
            field, due_date = due_field_info
            exact_timestamp = due_date.timestamp() if due_date else float("inf")
            # If descending, negate the timestamp
            if field.startswith("-"):
                exact_timestamp = -exact_timestamp if exact_timestamp != float("inf") else float("-inf")
            key_parts.append(exact_timestamp)

        # Add task ID as final tiebreaker to ensure deterministic sorting
        # This prevents tasks with identical sort keys from appearing in random order
        key_parts.append(task.id)

        return tuple(key_parts)

    # Sort all tasks using the configured sort order
    return sorted(tasks, key=get_sort_key)
