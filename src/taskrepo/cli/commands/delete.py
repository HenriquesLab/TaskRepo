"""Delete command for removing tasks."""

from typing import Tuple

import click
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.validation import Validator

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils.helpers import process_tasks_batch, update_cache_and_display_repo


@click.command(name="delete")
@click.argument("task_ids", nargs=-1, required=True)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def delete(ctx, task_ids: Tuple[str, ...], repo, force):
    """Delete one or more tasks permanently.

    Supports multiple tasks at once using space-separated or comma-separated IDs.

    Examples:
        tsk delete 4              # Delete task 4
        tsk delete 4 5 6          # Delete tasks 4, 5, and 6 (space-separated)
        tsk delete 4,5,6          # Delete tasks 4, 5, and 6 (comma-separated)
        tsk delete 10 --force     # Delete task 10 without confirmation

    TASK_IDS: One or more task IDs or titles to delete
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Flatten comma-separated task IDs to check if batch mode
    task_id_count = sum(len([tid.strip() for tid in task_id.split(",")]) for task_id in task_ids)
    is_batch = task_id_count > 1

    # Batch confirmation for multiple tasks (unless --force flag is used)
    if is_batch and not force:
        click.echo(f"\nAbout to delete {task_id_count} tasks. This cannot be undone.")

        # Create a validator for y/n input
        yn_validator = Validator.from_callable(
            lambda text: text.lower() in ["y", "n", "yes", "no"],
            error_message="Please enter 'y' or 'n'",
            move_cursor_to_end=True,
        )

        response = prompt(
            "Are you sure you want to proceed? (y/N) ",
            default="n",
            validator=yn_validator,
        ).lower()

        if response not in ["y", "yes"]:
            click.echo("Deletion cancelled.")
            ctx.exit(0)

    def delete_task_handler(task, repository):
        """Handler to delete a task with optional confirmation."""
        # Single task confirmation (only if not batch and not force)
        if not is_batch and not force:
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
            # Show success message for batch mode
            if is_batch:
                click.secho(f"✓ Deleted task: {task}", fg="green")
            return True, None
        else:
            return False, f"Failed to delete task '{task.id}'"

    # Use batch processor
    deleted_tasks, failed_tasks = process_tasks_batch(
        ctx, manager, task_ids, repo, task_handler=delete_task_handler, operation_name="deleted"
    )

    # Show summary for single task with detailed formatting
    if deleted_tasks and not is_batch and len(deleted_tasks) == 1:
        task, _ = deleted_tasks[0]
        assignees_str = f" {', '.join(task.assignees)}" if task.assignees else ""
        project_str = f" [{task.project}]" if task.project else ""
        success_msg = (
            f"{click.style('✓ Task deleted:', fg='green')} "
            f"{click.style('[' + task.id + ']', fg='cyan')} "
            f"{click.style(task.title, fg='yellow', bold=True)}"
            f"{project_str}{assignees_str} ({task.status}, {task.priority})"
        )
        click.echo(success_msg)

    # Update cache and display for affected repositories
    if deleted_tasks:
        repositories_to_update = {repo for _, repo in deleted_tasks}
        first_repo = list(repositories_to_update)[0]
        click.echo()
        update_cache_and_display_repo(manager, first_repo, config)
