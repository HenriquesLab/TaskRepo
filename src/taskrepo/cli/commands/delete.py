"""Delete command for removing tasks."""

import click
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.validation import Validator

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
        # Format task display with colored UUID and title
        assignees_str = f" {', '.join(task.assignees)}" if task.assignees else ""
        project_str = f" [{task.project}]" if task.project else ""
        task_display = (
            f"\nTask to delete: "
            f"{click.style('[' + task.id + ']', fg='cyan')} "
            f"{click.style(task.title, fg='yellow', bold=True)}"
            f"{project_str}{assignees_str} ({task.status}, {task.priority})"
        )
        click.echo(task_display)

        # Create a validator for y/n input
        yn_validator = Validator.from_callable(
            lambda text: text.lower() in ["y", "n", "yes", "no"],
            error_message="Please enter 'y' or 'n'",
            move_cursor_to_end=True,
        )

        response = prompt(
            "Are you sure you want to delete this task? This cannot be undone. (Y/n) ",
            default="y",
            validator=yn_validator,
        ).lower()

        if response not in ["y", "yes"]:
            click.echo("Deletion cancelled.")
            ctx.exit(0)

    # Delete the task
    if repository.delete_task(task.id):
        # Format success message with colored UUID and title
        assignees_str = f" {', '.join(task.assignees)}" if task.assignees else ""
        project_str = f" [{task.project}]" if task.project else ""
        success_msg = (
            f"{click.style('✓ Task deleted:', fg='green')} "
            f"{click.style('[' + task.id + ']', fg='cyan')} "
            f"{click.style(task.title, fg='yellow', bold=True)}"
            f"{project_str}{assignees_str} ({task.status}, {task.priority})"
        )
        click.echo(success_msg)
        click.echo()

        # Update cache and display repository tasks
        update_cache_and_display_repo(manager, repository, config)
    else:
        click.secho(f"Error: Failed to delete task '{task_id}'", fg="red", err=True)
        ctx.exit(1)
