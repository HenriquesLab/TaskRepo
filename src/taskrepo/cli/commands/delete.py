"""Delete command for removing tasks."""

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.helpers import normalize_task_id


@click.command(name="delete")
@click.argument("task_id")
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def delete(ctx, task_id, repo, force):
    """Delete a task permanently.

    TASK_ID: Task ID to delete
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Normalize task ID (convert "1" to "001", etc.)
    task_id = normalize_task_id(task_id)

    # Find the task
    if repo:
        repository = manager.get_repository(repo)
        if not repository:
            click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
            ctx.exit(1)
        task = repository.get_task(task_id)
        if not task:
            click.secho(f"Error: Task '{task_id}' not found in repository '{repo}'", fg="red", err=True)
            ctx.exit(1)
    else:
        # Search all repositories
        task = None
        repository = None
        for r in manager.discover_repositories():
            t = r.get_task(task_id)
            if t:
                task = t
                repository = r
                break

        if not task:
            click.secho(f"Error: Task '{task_id}' not found", fg="red", err=True)
            ctx.exit(1)

    # Confirmation prompt (unless --force flag is used)
    if not force:
        click.echo(f"\nTask to delete: {task}")
        if not click.confirm("Are you sure you want to delete this task? This cannot be undone.", default=False):
            click.echo("Deletion cancelled.")
            ctx.exit(0)

    # Delete the task
    if repository.delete_task(task_id):
        click.secho(f"✓ Task deleted: {task}", fg="green")
        click.echo()

        # Display all tasks in the repository
        all_tasks = repository.list_tasks()
        # Filter out completed tasks (consistent with default list behavior)
        active_tasks = [t for t in all_tasks if t.status != "completed"]

        if active_tasks:
            display_tasks_table(active_tasks, config)
    else:
        click.secho(f"Error: Failed to delete task '{task_id}'", fg="red", err=True)
        ctx.exit(1)
