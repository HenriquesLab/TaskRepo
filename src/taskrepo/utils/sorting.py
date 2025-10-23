"""Sorting utilities for tasks."""

from datetime import datetime
from typing import Any, Optional

from taskrepo.core.config import Config
from taskrepo.core.task import Task


def get_due_date_cluster(due_date: Optional[datetime]) -> int:
    """Convert due date to cluster bucket for sorting.

    Clusters tasks by countdown buckets (today, this week, this month, etc.)
    instead of exact timestamps. This allows grouping similar due dates together
    when sorting, so secondary sort fields (like priority) take precedence within each bucket.

    Args:
        due_date: Task due date

    Returns:
        Bucket number for clustering:
        -2: Overdue by 2+ weeks
        -1: Overdue by 1 week
         0: Overdue by 1-6 days
         1: Today
         2: Tomorrow
         3: 2-3 days
         4: 4-13 days
         5: 1-3 weeks (7-27 days)
         6: 1 month (28-59 days)
         7: 2+ months (60+ days)
         9: No due date
    """
    if not due_date:
        return 9  # No due date - sort last

    now = datetime.now()
    diff = due_date - now
    days = diff.days

    # Overdue
    if days < 0:
        abs_days = abs(days)
        if abs_days < 7:
            return 0  # Overdue by 1-6 days
        elif abs_days < 14:
            return -1  # Overdue by 1 week
        else:
            return -2  # Overdue by 2+ weeks

    # Future
    if days == 0:
        return 1  # Today
    if days == 1:
        return 2  # Tomorrow
    if days <= 3:
        return 3  # 2-3 days
    if days < 14:
        return 4  # 4-13 days
    if days < 28:
        return 5  # 1-3 weeks
    if days < 60:
        return 6  # 1 month
    return 7  # 2+ months


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
            status_order = {"pending": 0, "in_progress": 1, "completed": 2, "cancelled": 3}
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
                first_assignee = task.assignees[0].lower()
                value = (0, first_assignee)
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

        for field in sort_fields:
            is_desc, value = get_field_value(task, field)
            key_parts.append(value)

            # When clustering is enabled and this is the 'due' field,
            # add exact timestamp as tiebreaker within same bucket
            if config.cluster_due_dates and field.lstrip("-") == "due":
                exact_timestamp = task.due.timestamp() if task.due else float("inf")
                # If descending, negate the timestamp
                if field.startswith("-"):
                    exact_timestamp = -exact_timestamp if exact_timestamp != float("inf") else float("-inf")
                key_parts.append(exact_timestamp)

        return tuple(key_parts)

    # Sort all tasks using the configured sort order
    return sorted(tasks, key=get_sort_key)
