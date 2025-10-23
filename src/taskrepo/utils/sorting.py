"""Sorting utilities for tasks."""

from taskrepo.core.config import Config
from taskrepo.core.task import Task


def sort_tasks(tasks: list[Task], config: Config) -> list[Task]:
    """Sort tasks according to configuration settings.

    Args:
        tasks: List of tasks to sort
        config: Configuration object containing sort_by settings

    Returns:
        Sorted list of tasks
    """

    def get_field_value(task: Task, field: str) -> tuple[bool, any]:
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

        return tuple(key_parts)

    # Sort all tasks using the configured sort order
    return sorted(tasks, key=get_sort_key)
