"""Delete command for removing tasks."""

from typing import Tuple

import click
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.validation import Validator

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result, update_cache_and_display_repo


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

    # Flatten comma-separated task IDs (supports both "4 5 6" and "4,5,6")
    task_id_list = []
    for task_id in task_ids:
        task_id_list.extend([tid.strip() for tid in task_id.split(",")])

    is_batch = len(task_id_list) > 1

    # Batch confirmation for multiple tasks (unless --force flag is used)
    if is_batch and not force:
        click.echo(f"\nAbout to delete {len(task_id_list)} tasks. This cannot be undone.")

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

    # Track results
    deleted_tasks = []
    failed_tasks = []
    repositories_to_update = set()

    for task_id in task_id_list:
        try:
            # Try to find task by ID or title
            result = find_task_by_title_or_id(manager, task_id, repo)

            # Handle not found
            if result[0] is None:
                if is_batch:
                    click.secho(f"✗ No task found matching '{task_id}'", fg="red")
                    failed_tasks.append(task_id)
                    continue
                else:
                    click.secho(f"Error: No task found matching '{task_id}'", fg="red", err=True)
                    ctx.exit(1)

            # Handle multiple matches
            elif isinstance(result[0], list):
                if is_batch:
                    click.secho(f"✗ Multiple tasks found matching '{task_id}' - skipping", fg="red")
                    failed_tasks.append(task_id)
                    continue
                else:
                    # Let select_task_from_result handle the interactive selection
                    task, repository = select_task_from_result(ctx, result, task_id)
            else:
                # Single match found
                task, repository = result

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
                deleted_tasks.append((task, repository))
                repositories_to_update.add(repository)

                # Show success message for single task or batch
                if is_batch:
                    click.secho(f"✓ Deleted task: {task}", fg="green")
            else:
                if is_batch:
                    click.secho(f"✗ Failed to delete task '{task_id}'", fg="red")
                    failed_tasks.append(task_id)
                else:
                    click.secho(f"Error: Failed to delete task '{task_id}'", fg="red", err=True)
                    ctx.exit(1)

        except Exception as e:
            # Unexpected error - show message and continue with next task
            failed_tasks.append(task_id)
            if is_batch:
                click.secho(f"✗ Could not delete task '{task_id}': {e}", fg="red")
            else:
                click.secho(f"Error: Could not delete task '{task_id}': {e}", fg="red", err=True)
                ctx.exit(1)

    # Show summary
    if deleted_tasks:
        # For single task, show detailed success message
        if not is_batch and len(deleted_tasks) == 1:
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

        # Show batch summary
        if is_batch:
            click.echo()
            click.secho(f"Deleted {len(deleted_tasks)} of {len(task_id_list)} tasks", fg="green")

    # Update cache and display for affected repositories
    if repositories_to_update:
        first_repo = list(repositories_to_update)[0]
        click.echo()
        update_cache_and_display_repo(manager, first_repo, config)

    # Exit with error code if any failures (only in non-batch mode)
    if failed_tasks and not is_batch:
        ctx.exit(1)
