"""Delete command for removing tasks."""

import click
from prompt_toolkit.shortcuts import confirm

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result, update_cache_and_display_repo


@click.command(name="delete")
@click.argument("task_id")
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def delete(ctx, task_id, repo, force):
    """Delete a task permanently.

    TASK_ID: Task ID or title to delete
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Try to find task by ID or title
    result = find_task_by_title_or_id(manager, task_id, repo)
    task, repository = select_task_from_result(ctx, result, task_id)

    # Confirmation prompt (unless --force flag is used)
    if not force:
        click.echo(f"\nTask to delete: {task}")
        if not confirm("Are you sure you want to delete this task? This cannot be undone."):
            click.echo("Deletion cancelled.")
            ctx.exit(0)

    # Delete the task
    if repository.delete_task(task.id):
        click.secho(f"✓ Task deleted: {task}", fg="green")
        click.echo()

        # Update cache and display repository tasks
        update_cache_and_display_repo(manager, repository, config)
    else:
        click.secho(f"Error: Failed to delete task '{task_id}'", fg="red", err=True)
        ctx.exit(1)
