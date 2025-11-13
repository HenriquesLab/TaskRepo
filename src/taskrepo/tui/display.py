"""Display utilities for rendering task tables."""

from datetime import datetime

import wcwidth
from rich.console import Console
from rich.table import Table

from taskrepo.core.config import Config
from taskrepo.core.task import Task
from taskrepo.utils.display_constants import PRIORITY_COLORS, STATUS_COLORS
from taskrepo.utils.id_mapping import get_display_id_from_uuid, save_id_cache
from taskrepo.utils.sorting import sort_tasks


def display_width(text: str) -> int:
    """Calculate the display width of a string, accounting for emojis and wide characters.

    Args:
        text: String to measure

    Returns:
        Display width in terminal cells (emojis typically count as 2)
    """
    width = wcwidth.wcswidth(text)
    # wcswidth returns -1 if there are non-printable characters or unrecognized sequences
    if width >= 0:
        return width

    # Fall back to character-by-character calculation
    # This handles mixed content (emojis, box-drawing chars, etc.) more reliably
    total = 0
    for char in text:
        char_width = wcwidth.wcwidth(char)
        if char_width < 0:
            # Unrecognized character, assume width of 1
            total += 1
        else:
            total += char_width
    return total


def truncate_to_width(text: str, max_width: int, suffix: str = "...") -> str:
    """Truncate a string to fit within a specific display width.

    Args:
        text: String to truncate
        max_width: Maximum display width
        suffix: Suffix to add when truncating (default: "...")

    Returns:
        Truncated string that fits within max_width cells
    """
    current_width = display_width(text)

    if current_width <= max_width:
        return text

    # Need to truncate - account for suffix width
    suffix_width = display_width(suffix)
    target_width = max_width - suffix_width

    if target_width <= 0:
        # Not enough space for suffix
        return suffix[:max_width]

    # Build truncated string character by character
    result = ""
    current = 0

    for char in text:
        char_width = wcwidth.wcwidth(char)
        # wcwidth returns -1 for control chars, treat as 1
        if char_width < 0:
            char_width = 1

        if current + char_width > target_width:
            break

        result += char
        current += char_width

    return result + suffix


def pad_to_width(text: str, target_width: int, align: str = "left") -> str:
    """Pad a string to a specific display width.

    Args:
        text: String to pad
        target_width: Target display width
        align: Alignment - "left" or "right"

    Returns:
        Padded string that displays at exactly target_width cells
    """
    current_width = display_width(text)

    if current_width >= target_width:
        return text

    padding = " " * (target_width - current_width)

    if align == "right":
        return padding + text
    else:  # left (default)
        return text + padding


def get_countdown_text(due_date: datetime, status: str = None) -> tuple[str, str]:
    """Calculate countdown text and color from a due date.

    Args:
        due_date: The due date to calculate countdown for
        status: Task status (if completed/cancelled, return neutral text)

    Returns:
        Tuple of (countdown_text, color_name)
        Format: "2 days", "1 week", "3 months"
    """
    from taskrepo.utils.countdown import calculate_countdown, format_countdown_for_display

    # For completed or cancelled tasks, show neutral status instead of countdown
    if status == "completed":
        return "✓", "green"
    elif status == "cancelled":
        return "-", "red"

    # Use centralized countdown calculation
    countdown_text, countdown_status, _ = calculate_countdown(due_date)
    return format_countdown_for_display(countdown_text, countdown_status)


def build_task_tree(tasks: list[Task], config: Config) -> list[tuple[Task, int, bool, list[bool]]]:
    """Build a hierarchical tree structure from a flat list of tasks.

    Args:
        tasks: Flat list of Task objects
        config: Configuration object for sorting preferences

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

    # Sort children within each parent
    # For subtasks, prioritize due date first, then apply the configured sort order
    # This ensures urgent subtasks appear first regardless of other sort criteria
    for parent_id in children_map:
        # Create a temporary config that prioritizes due date for subtasks
        # IMPORTANT: Modify _data directly to avoid triggering config.save()
        subtask_config = Config()
        subtask_config._data["sort_by"] = ["due"] + [f for f in config.sort_by if f.lstrip("-") != "due"]
        subtask_config._data["cluster_due_dates"] = config.cluster_due_dates
        children_map[parent_id] = sort_tasks(children_map[parent_id], subtask_config, all_tasks=tasks)

    # Recursive function to build tree
    def add_to_tree(task: Task, depth: int, ancestor_positions: list[bool], result: list):
        # Determine if this is the last child
        is_last = False
        if task.parent and task.parent in task_dict:
            siblings = children_map.get(task.parent, [])
            is_last = siblings and task.id == siblings[-1].id

        result.append((task, depth, is_last, ancestor_positions.copy()))

        # Add children (already sorted)
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
    show_completed_date: bool = False,
) -> None:
    """Display tasks in a Rich formatted table.

    Args:
        tasks: List of tasks to display
        config: Configuration object for sorting preferences
        title: Optional custom title for the table
        tree_view: Whether to show hierarchical tree structure (default: True)
        save_cache: Whether to save the ID mapping cache (default: True, set to False for filtered views)
        id_offset: Offset to add to display IDs (used for showing completed tasks after active tasks)
        show_completed_date: If True, show "Completed" date instead of "Countdown" (for completed tasks)
    """
    if not tasks:
        return

    # Sort tasks (for tree view, only sort top-level tasks)
    if tree_view:
        # Separate top-level and subtasks
        top_level = [t for t in tasks if not t.parent]
        subtasks = [t for t in tasks if t.parent]

        # Sort top-level tasks using centralized sorting utility
        # Pass all tasks for effective due date calculation (includes subtasks)
        sorted_top_level = sort_tasks(top_level, config, all_tasks=tasks)

        # Build tree structure (subtasks will be sorted within their parents)
        tree_items = build_task_tree(sorted_top_level + subtasks, config)

        # Extract tasks in tree order for display
        display_tasks = [item[0] for item in tree_items]
    else:
        # Flat view: sort all tasks normally using centralized sorting utility
        sorted_tasks = sort_tasks(tasks, config, all_tasks=tasks)
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
    # Change column name based on show_completed_date flag
    if show_completed_date:
        table.add_column("Completed", no_wrap=True)
    else:
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
            # Get display ID from cache (for both filtered and unfiltered views)
            # This ensures consistency: tsk add and tsk list show the same IDs
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

        # Format countdown or completed date
        if show_completed_date:
            # Show when task was completed (modified date)
            if task.status == "completed":
                countdown_str = task.modified.strftime("%Y-%m-%d")
            else:
                countdown_str = "-"
        else:
            # Show countdown (existing logic)
            if task.due:
                countdown_text, countdown_color = get_countdown_text(task.due, task.status)
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
