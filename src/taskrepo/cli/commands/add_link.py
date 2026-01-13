"""Add-link command for adding URLs to task links."""

from typing import Optional

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result


@click.command(name="add-link")
@click.argument("task_id", required=True)
@click.argument("url", required=True)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def add_link(ctx, task_id: str, url: str, repo: Optional[str]):
    """Add a link/URL to a task.

    Examples:
        tsk add-link 5 "https://github.com/org/repo/issues/123"
        tsk add-link 10 "https://mail.google.com/..." --repo work

    TASK_ID: Task ID, UUID, or title
    URL: URL to add to task links
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Validate URL format
    if not url.startswith(("http://", "https://")):
        click.secho("Error: URL must start with http:// or https://", fg="red", err=True)
        ctx.exit(1)

    # Find task
    result = find_task_by_title_or_id(manager, task_id, repo)

    if result[0] is None:
        click.secho(f"Error: No task found matching '{task_id}'", fg="red", err=True)
        ctx.exit(1)

    task, repository = select_task_from_result(ctx, result, task_id)

    # Add link if not already present
    if task.links is None:
        task.links = []

    if url in task.links:
        click.secho(f"Link already exists in task: {task.title}", fg="yellow")
        ctx.exit(0)

    task.links.append(url)

    # Save task
    repository.save_task(task)

    click.secho(f"✓ Added link to task: {task.title}", fg="green")
    click.echo(f"\nLink added: {url}")
    click.echo(f"Total links: {len(task.links)}")
