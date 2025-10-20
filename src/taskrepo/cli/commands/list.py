"""List command for displaying tasks."""

import click
from rich.console import Console
from rich.table import Table

from taskrepo.core.repository import RepositoryManager


@click.command(name="list")
@click.option("--repo", "-r", help="Filter by repository")
@click.option("--project", "-p", help="Filter by project")
@click.option("--status", "-s", help="Filter by status")
@click.option("--priority", type=click.Choice(["H", "M", "L"], case_sensitive=False), help="Filter by priority")
@click.option("--assignee", "-a", help="Filter by assignee")
@click.option("--tag", "-t", help="Filter by tag")
@click.option("--all", "show_all", is_flag=True, help="Show all tasks (including completed)")
@click.pass_context
def list_tasks(ctx, repo, project, status, priority, assignee, tag, show_all):
    """List tasks with optional filters."""
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Get tasks
    if repo:
        repository = manager.get_repository(repo)
        if not repository:
            click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
            ctx.exit(1)
        tasks = repository.list_tasks()
    else:
        tasks = manager.list_all_tasks()

    # Apply filters
    if not show_all:
        tasks = [t for t in tasks if t.status != "completed"]

    if project:
        tasks = [t for t in tasks if t.project == project]

    if status:
        tasks = [t for t in tasks if t.status == status]

    if priority:
        tasks = [t for t in tasks if t.priority.upper() == priority.upper()]

    if assignee:
        if not assignee.startswith("@"):
            assignee = f"@{assignee}"
        tasks = [t for t in tasks if assignee in t.assignees]

    if tag:
        tasks = [t for t in tasks if tag in t.tags]

    # Display results
    if not tasks:
        click.echo("No tasks found.")
        return

    # Create Rich table
    console = Console()
    table = Table(title=f"Tasks ({len(tasks)} found)", show_lines=True)

    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Repo", style="magenta")
    table.add_column("Project", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("Priority", justify="center")
    table.add_column("Assignees", style="green")
    table.add_column("Tags", style="dim")
    table.add_column("Due", style="red")

    for task in sorted(tasks, key=lambda t: (t.repo or "", t.id)):
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

        table.add_row(
            task.id,
            task.title,
            task.repo or "-",
            task.project or "-",
            status_str,
            priority_str,
            assignees_str,
            tags_str,
            due_str,
        )

    console.print(table)
