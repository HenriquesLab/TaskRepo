"""Append command for adding content to task descriptions."""

import sys
from typing import Optional

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result


@click.command()
@click.argument("task_id", required=True)
@click.option("--text", "-t", required=True, help="Text to append to task description")
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def append(ctx, task_id: str, text: str, repo: Optional[str]):
    """Append text to a task's description.

    Examples:
        tsk append 5 --text "Additional note from meeting"
        tsk append 10 -t "Updated requirements" --repo work

    TASK_ID: Task ID, UUID, or title to append to
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Find task
    result = find_task_by_title_or_id(manager, task_id, repo)

    if result[0] is None:
        click.secho(f"Error: No task found matching '{task_id}'", fg="red", err=True)
        ctx.exit(1)

    task, repository = select_task_from_result(ctx, result, task_id)

    # Append text to description
    if task.description:
        task.description = task.description.rstrip() + "\n\n" + text
    else:
        task.description = text

    # Save task
    repository.save_task(task)

    click.secho(f"✓ Appended text to task: {task.title}", fg="green")
    click.echo(f"\nNew content added:")
    click.echo(f"  {text}")
