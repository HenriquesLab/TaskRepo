"""Display utilities for rendering task tables."""

from datetime import datetime

from rich.console import Console
from rich.table import Table

from taskrepo.core.config import Config
from taskrepo.core.task import Task
from taskrepo.utils.id_mapping import save_id_cache


def get_countdown_text(due_date: datetime) -> tuple[str, str]:
    """Calculate countdown text and color from a due date.

    Args:
        due_date: The due date to calculate countdown for

    Returns:
        Tuple of (countdown_text, color_name)
    """
    now = datetime.now()
    diff = due_date - now
    days = diff.days
    hours = diff.seconds // 3600

    # Handle overdue
    if days < 0:
        abs_days = abs(days)
        if abs_days == 1:
            text = "overdue by 1 day"
        elif abs_days < 7:
            text = f"overdue by {abs_days} days"
        elif abs_days < 14:
            text = "overdue by 1 week"
        else:
            weeks = abs_days // 7
            text = f"overdue by {weeks} weeks"
        return text, "red"

    # Handle today
    if days == 0:
        if hours < 1:
            text = "due now"
        else:
            text = "today"
        return text, "yellow"

    # Handle tomorrow
    if days == 1:
        return "tomorrow", "yellow"

    # Handle within 3 days (urgent)
    if days <= 3:
        return f"{days} days", "yellow"

    # Handle within 2 weeks
    if days < 14:
        return f"{days} days", "green"

    # Handle weeks
    weeks = days // 7
    if weeks == 1:
        return "1 week", "green"
    elif weeks < 4:
        return f"{weeks} weeks", "green"

    # Handle months
    months = days // 30
    if months == 1:
        return "1 month", "green"
    else:
        return f"{months} months", "green"


def display_tasks_table(tasks: list[Task], config: Config, title: str = None) -> None:
    """Display tasks in a Rich formatted table.

    Args:
        tasks: List of tasks to display
        config: Configuration object for sorting preferences
        title: Optional custom title for the table
    """
    if not tasks:
        return

    # Sort tasks using configured sort order
    def get_field_value(task, field):
        """Get sortable value for a field."""
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
        else:
            value = ""

        # Reverse for descending order
        if descending:
            if isinstance(value, (int, float)):
                value = -value if value != float("inf") else float("-inf")
            elif isinstance(value, str):
                # For strings, we'll reverse the sort later
                return (True, value)  # Flag as descending

        return (False, value) if not descending else (True, value)

    def get_sort_key(task):
        sort_fields = config.sort_by
        key_parts = [task.repo or ""]  # Always group by repo first

        for field in sort_fields:
            is_desc, value = get_field_value(task, field)
            key_parts.append(value)

        return tuple(key_parts)

    sorted_tasks = sorted(tasks, key=get_sort_key)

    # Save display ID mapping
    save_id_cache(sorted_tasks)

    # Create Rich table
    console = Console()
    table_title = title or f"Tasks ({len(sorted_tasks)} found)"
    table = Table(title=table_title, show_lines=True)

    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Repo", style="magenta")
    table.add_column("Project", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("Priority", justify="center")
    table.add_column("Assignees", style="green")
    table.add_column("Tags", style="dim")
    table.add_column("Due", style="red")
    table.add_column("Countdown", no_wrap=True)

    for display_id, task in enumerate(sorted_tasks, start=1):
        # Format priority with color
        priority_color = {"H": "red", "M": "yellow", "L": "green"}.get(task.priority, "white")
        priority_str = f"[{priority_color}]{task.priority}[/{priority_color}]"

        # Format status with color
        status_color = {
            "pending": "yellow",
            "in_progress": "blue",
            "completed": "green",
            "cancelled": "red",
        }.get(task.status, "white")
        status_str = f"[{status_color}]{task.status}[/{status_color}]"

        # Format assignees
        assignees_str = ", ".join(task.assignees) if task.assignees else "-"

        # Format tags
        tags_str = ", ".join(task.tags) if task.tags else "-"

        # Format due date
        due_str = task.due.strftime("%Y-%m-%d") if task.due else "-"

        # Format countdown
        if task.due:
            countdown_text, countdown_color = get_countdown_text(task.due)
            countdown_str = f"[{countdown_color}]{countdown_text}[/{countdown_color}]"
        else:
            countdown_str = "-"

        table.add_row(
            str(display_id),
            task.title,
            task.repo or "-",
            task.project or "-",
            status_str,
            priority_str,
            assignees_str,
            tags_str,
            due_str,
            countdown_str,
        )

    console.print(table)
