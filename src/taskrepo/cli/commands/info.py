"""Info command for displaying detailed task information."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils.display_constants import PRIORITY_COLORS, PRIORITY_EMOJIS, STATUS_COLORS, STATUS_EMOJIS
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result


@click.command()
@click.argument("task_id")
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def info(ctx, task_id, repo):
    """Display detailed information about a specific task.

    TASK_ID: Task ID or title to display information for
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Try to find task by ID or title
    result = find_task_by_title_or_id(manager, task_id, repo)
    task, repository = select_task_from_result(ctx, result, task_id)

    # Create Rich console
    console = Console()

    # Build detailed display
    console.print()

    # Title header
    title = Text()
    title.append(task.title, style="bold cyan")
    console.print(Panel(title, border_style="cyan"))

    # Main details table
    details_table = Table(show_header=False, box=None, padding=(0, 2))
    details_table.add_column("Field", style="bold yellow", no_wrap=True)
    details_table.add_column("Value", style="white")

    # UUID
    details_table.add_row("UUID", f"[dim]{task.id}[/dim]")

    # Repository
    details_table.add_row("Repository", task.repo or "-")

    # File path
    task_file_path = repository.tasks_dir / f"task-{task.id}.md"
    details_table.add_row("File Path", f"[dim]{task_file_path}[/dim]")

    # Status
    status_color = STATUS_COLORS.get(task.status, "white")
    status_emoji = STATUS_EMOJIS.get(task.status, "")
    details_table.add_row("Status", f"[{status_color}]{status_emoji} {task.status}[/{status_color}]")

    # Priority
    priority_color = PRIORITY_COLORS.get(task.priority, "white")
    priority_emoji = PRIORITY_EMOJIS.get(task.priority, "")
    details_table.add_row("Priority", f"[{priority_color}]{priority_emoji} {task.priority}[/{priority_color}]")

    # Project
    if task.project:
        details_table.add_row("Project", f"[blue]{task.project}[/blue]")

    # Assignees
    if task.assignees:
        assignees_str = ", ".join([f"[green]{a}[/green]" for a in task.assignees])
        details_table.add_row("Assignees", assignees_str)

    # Tags
    if task.tags:
        tags_str = ", ".join([f"[dim]{t}[/dim]" for t in task.tags])
        details_table.add_row("Tags", tags_str)

    # Links
    if task.links:
        for i, link in enumerate(task.links):
            label = "Links" if i == 0 else ""
            details_table.add_row(label, f"[link={link}]🔗 {link}[/link]")

    # Due date
    if task.due:
        from datetime import datetime

        now = datetime.now()
        diff = task.due - now
        days = diff.days

        if days < 0:
            due_color = "red"
            due_emoji = "⚠️"
        elif days <= 3:
            due_color = "yellow"
            due_emoji = "⏰"
        else:
            due_color = "green"
            due_emoji = "📅"

        due_str = task.due.strftime("%Y-%m-%d %H:%M")
        details_table.add_row("Due Date", f"[{due_color}]{due_emoji} {due_str}[/{due_color}]")

    # Created & Modified
    created_str = task.created.strftime("%Y-%m-%d %H:%M")
    modified_str = task.modified.strftime("%Y-%m-%d %H:%M")
    details_table.add_row("Created", f"[dim]{created_str}[/dim]")
    details_table.add_row("Modified", f"[dim]{modified_str}[/dim]")

    # Dependencies
    if task.depends:
        for i, dep_id in enumerate(task.depends):
            label = "Depends On" if i == 0 else ""
            details_table.add_row(label, f"[cyan]{dep_id}[/cyan]")

    # Parent task
    if task.parent:
        parent_task = repository.get_task(task.parent)
        if parent_task:
            details_table.add_row("Parent Task", f"[magenta]{task.parent[:8]}... - {parent_task.title}[/magenta]")
        else:
            details_table.add_row("Parent Task", f"[magenta]{task.parent}[/magenta]")

    # Subtasks
    subtasks = repository.get_subtasks(task.id)
    if subtasks:
        for i, subtask in enumerate(subtasks):
            label = "Subtasks" if i == 0 else ""
            status_icon = STATUS_EMOJIS.get(subtask.status, "")
            details_table.add_row(label, f"[cyan]{status_icon} {subtask.id[:8]}... - {subtask.title}[/cyan]")

    console.print(details_table)

    # Description
    if task.description:
        console.print()
        console.print(Panel(task.description, title="Description", border_style="green"))

    console.print()
