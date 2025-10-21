"""Done command for marking tasks as completed."""

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.helpers import normalize_task_id


@click.command()
@click.argument("task_id", required=False)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def done(ctx, task_id, repo):
    """Mark a task as completed, or list completed tasks if no task ID is provided.

    TASK_ID: Task ID to mark as done (optional - if omitted, lists completed tasks)
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # If no task_id provided, list completed tasks
    if task_id is None:
        # Get tasks from specified repo or all repos
        if repo:
            repository = manager.get_repository(repo)
            if not repository:
                click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
                ctx.exit(1)
            tasks = repository.list_tasks()
        else:
            tasks = manager.list_all_tasks()

        # Filter to only completed tasks
        completed_tasks = [t for t in tasks if t.status == "completed"]

        if not completed_tasks:
            repo_msg = f" in repository '{repo}'" if repo else ""
            click.echo(f"No completed tasks found{repo_msg}.")
            return

        # Display completed tasks
        display_tasks_table(completed_tasks, config, title=f"Completed Tasks ({len(completed_tasks)} found)")
        return

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

    # Mark as completed
    task.status = "completed"
    repository.save_task(task)

    click.secho(f"✓ Task marked as completed: {task}", fg="green")
    click.echo()

    # Display all tasks in the repository
    all_tasks = repository.list_tasks()
    # Filter out completed tasks (consistent with default list behavior)
    active_tasks = [t for t in all_tasks if t.status != "completed"]

    if active_tasks:
        display_tasks_table(active_tasks, config)
