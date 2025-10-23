"""Display utilities for rendering task tables."""

from datetime import datetime

from rich.console import Console
from rich.table import Table

from taskrepo.core.config import Config
from taskrepo.core.task import Task
from taskrepo.utils.display_constants import PRIORITY_COLORS, STATUS_COLORS
from taskrepo.utils.id_mapping import get_display_id_from_uuid, save_id_cache
from taskrepo.utils.sorting import sort_tasks


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


def build_task_tree(tasks: list[Task]) -> list[tuple[Task, int, bool, list[bool]]]:
    """Build a hierarchical tree structure from a flat list of tasks.

    Args:
        tasks: Flat list of Task objects

    Returns:
        List of tuples: (task, depth, is_last_child, ancestor_positions)
        - depth: Nesting level (0 for top-level)
        - is_last_child: Whether this task is the last child of its parent
        - ancestor_positions: List of booleans indicating if ancestors are last children
    """
    # Build parent-child relationships
    task_dict = {task.id: task for task in tasks}
    children_map = {}

    for task in tasks:
        if task.parent:
            if task.parent not in children_map:
                children_map[task.parent] = []
            children_map[task.parent].append(task)

    # Recursive function to build tree
    def add_to_tree(task: Task, depth: int, ancestor_positions: list[bool], result: list):
        # Determine if this is the last child
        is_last = False
        if task.parent and task.parent in task_dict:
            siblings = children_map.get(task.parent, [])
            is_last = siblings and task.id == siblings[-1].id

        result.append((task, depth, is_last, ancestor_positions.copy()))

        # Add children
        children = children_map.get(task.id, [])
        for child in children:
            new_ancestors = ancestor_positions + [is_last]
            add_to_tree(child, depth + 1, new_ancestors, result)

    # Build tree starting from top-level tasks (no parent)
    result = []
    top_level_tasks = [t for t in tasks if not t.parent]

    for task in top_level_tasks:
        add_to_tree(task, 0, [], result)

    return result


def count_subtasks(task: Task, tasks: list[Task]) -> int:
    """Count the number of direct subtasks for a given task.

    Args:
        task: Parent task
        tasks: List of all tasks

    Returns:
        Number of direct children
    """
    return sum(1 for t in tasks if t.parent == task.id)


def format_tree_title(title: str, depth: int, is_last: bool, ancestor_positions: list[bool], subtask_count: int) -> str:
    """Format a task title with tree indentation and characters.

    Args:
        title: Original task title
        depth: Nesting depth (0 for top-level)
        is_last: Whether this is the last child of its parent
        ancestor_positions: List of booleans indicating if ancestors are last children
        subtask_count: Number of direct subtasks (0 if none)

    Returns:
        Formatted title with tree characters
    """
    if depth == 0:
        # Top-level task
        if subtask_count > 0:
            return f"{title} 📋 {subtask_count}"
        return title

    # For direct children (depth 1), only show branch without ancestor lines
    if depth == 1:
        branch = "└─ " if is_last else "├─ "
        if subtask_count > 0:
            return f"{branch}{title} 📋 {subtask_count}"
        return f"{branch}{title}"

    # For deeper nesting, add ancestor lines
    prefix = ""

    # Skip the first ancestor (parent is top-level)
    for is_ancestor_last in ancestor_positions[1:]:
        if is_ancestor_last:
            prefix += "   "  # No vertical line if ancestor was last
        else:
            prefix += "│  "  # Vertical line continuation

    # Add branch character for this level
    if is_last:
        prefix += "└─ "  # Last child
    else:
        prefix += "├─ "  # Middle child

    # Add subtask count if this task has children
    if subtask_count > 0:
        return f"{prefix}{title} 📋 {subtask_count}"

    return f"{prefix}{title}"


def display_tasks_table(
    tasks: list[Task],
    config: Config,
    title: str = None,
    tree_view: bool = True,
    save_cache: bool = True,
    id_offset: int = 0,
) -> None:
    """Display tasks in a Rich formatted table.

    Args:
        tasks: List of tasks to display
        config: Configuration object for sorting preferences
        title: Optional custom title for the table
        tree_view: Whether to show hierarchical tree structure (default: True)
        save_cache: Whether to save the ID mapping cache (default: True, set to False for filtered views)
        id_offset: Offset to add to display IDs (used for showing completed tasks after active tasks)
    """
    if not tasks:
        return

    # Sort tasks (for tree view, only sort top-level tasks)
    if tree_view:
        # Separate top-level and subtasks
        top_level = [t for t in tasks if not t.parent]
        subtasks = [t for t in tasks if t.parent]

        # Sort top-level tasks using centralized sorting utility
        sorted_top_level = sort_tasks(top_level, config)

        # Build tree structure
        tree_items = build_task_tree(sorted_top_level + subtasks)

        # Extract tasks in tree order for display
        display_tasks = [item[0] for item in tree_items]
    else:
        # Flat view: sort all tasks normally using centralized sorting utility
        sorted_tasks = sort_tasks(tasks, config)
        display_tasks = sorted_tasks
        tree_items = [(task, 0, False, []) for task in sorted_tasks]

    # Save display ID mapping (only for unfiltered views to maintain consistency)
    if save_cache:
        save_id_cache(display_tasks)

    # Create Rich table
    console = Console()
    table_title = title or f"Tasks ({len(display_tasks)} found)"
    table = Table(title=table_title, show_lines=True)

    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("🔗", justify="center", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Repo", style="magenta")
    table.add_column("Project", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("Priority", justify="center")
    table.add_column("Assignees", style="green")
    table.add_column("Tags", style="dim")
    table.add_column("Due", style="red")
    table.add_column("Countdown", no_wrap=True)

    for idx, (task, depth, is_last, ancestors) in enumerate(
        zip(
            display_tasks,
            [item[1] for item in tree_items],
            [item[2] for item in tree_items],
            [item[3] for item in tree_items],
            strict=False,
        ),
        start=1,
    ):
        # Get display ID
        if id_offset > 0:
            # Use offset-based sequential IDs (for completed tasks shown after active tasks)
            display_id_str = str(id_offset + idx)
        else:
            # Get display ID from cache (or show UUID prefix if not in cache)
            display_id = get_display_id_from_uuid(task.id)
            if display_id is None:
                # Task not in cache (e.g., newly added), show first 8 chars of UUID
                display_id_str = f"{task.id[:8]}..."
            else:
                display_id_str = str(display_id)

        # Format title with tree structure
        if tree_view:
            subtask_count = count_subtasks(task, tasks)
            formatted_title = format_tree_title(task.title, depth, is_last, ancestors, subtask_count)
        else:
            formatted_title = task.title

        # Format priority with color
        priority_color = PRIORITY_COLORS.get(task.priority, "white")
        priority_str = f"[{priority_color}]{task.priority}[/{priority_color}]"

        # Format status with color
        status_color = STATUS_COLORS.get(task.status, "white")
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

        # Format links indicator
        links_indicator = "🔗" if task.links else "-"

        table.add_row(
            display_id_str,
            links_indicator,
            formatted_title,
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
