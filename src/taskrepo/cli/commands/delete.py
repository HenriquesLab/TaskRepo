"""Delete command for removing tasks."""

import click
from prompt_toolkit.shortcuts import confirm

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.helpers import find_task_by_title_or_id
from taskrepo.utils.id_mapping import save_id_cache


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

    if result[0] is None:
        # Not found
        click.secho(f"Error: No task found matching '{task_id}'", fg="red", err=True)
        ctx.exit(1)
    elif isinstance(result[0], list):
        # Multiple matches - ask user to select
        click.echo(f"\nMultiple tasks found matching '{task_id}':")
        for idx, (t, r) in enumerate(zip(result[0], result[1], strict=False), start=1):
            click.echo(f"  {idx}. [{t.id[:8]}...] {t.title} (repo: {r.name})")

        try:
            choice = click.prompt("\nSelect task number", type=int)
            if choice < 1 or choice > len(result[0]):
                click.secho("Invalid selection", fg="red", err=True)
                ctx.exit(1)
            task = result[0][choice - 1]
            repository = result[1][choice - 1]
        except (ValueError, click.Abort):
            click.echo("Cancelled.")
            ctx.exit(0)
    else:
        # Single match found
        task, repository = result

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

        # Update cache with ALL active tasks across all repos
        all_tasks_all_repos = manager.list_all_tasks()
        active_tasks_all = [t for t in all_tasks_all_repos if t.status != "completed"]
        save_id_cache(active_tasks_all)

        # Display tasks from this repository only (filtered view)
        repo_tasks = repository.list_tasks()
        active_tasks_repo = [t for t in repo_tasks if t.status != "completed"]

        if active_tasks_repo:
            display_tasks_table(active_tasks_repo, config, save_cache=False)
    else:
        click.secho(f"Error: Failed to delete task '{task_id}'", fg="red", err=True)
        ctx.exit(1)
