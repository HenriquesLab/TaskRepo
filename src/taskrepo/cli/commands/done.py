"""Done command for marking tasks as completed."""

import click

from taskrepo.core.repository import RepositoryManager


@click.command()
@click.argument("task_id")
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def done(ctx, task_id, repo):
    """Mark a task as completed.

    TASK_ID: Task ID to mark as done
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

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
