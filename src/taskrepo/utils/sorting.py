"""Sorting utilities for tasks."""

from datetime import datetime
from typing import Any, Optional

from taskrepo.core.config import Config
from taskrepo.core.task import Task


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


def sort_tasks(tasks: list[Task], config: Config) -> list[Task]:
    """Sort tasks according to configuration settings.

    Args:
        tasks: List of tasks to sort
        config: Configuration object containing sort_by settings

    Returns:
        Sorted list of tasks
    """

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
            if config.cluster_due_dates:
                # Use cluster bucket instead of exact timestamp
                value = get_due_date_cluster(task.due)
            else:
                # Use exact timestamp
                value = task.due.timestamp() if task.due else float("inf")
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
                due_field_info = (field, task.due)

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
