"""List command for displaying tasks."""

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table


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

    # Display tasks using shared display function
    display_tasks_table(tasks, config)
