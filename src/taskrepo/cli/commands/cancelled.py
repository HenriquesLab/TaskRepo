"""Cancelled command for marking tasks as cancelled."""

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils.helpers import (
    find_task_by_title_or_id,
    prompt_for_subtask_unarchiving,
    select_task_from_result,
    update_cache_and_display_repo,
)


@click.command()
@click.argument("task_ids", nargs=-1, required=True)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def cancelled(ctx, task_ids, repo):
    """Mark one or more tasks as cancelled.

    TASK_IDS: One or more task IDs to mark as cancelled (comma-separated)
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Parse comma-separated task IDs
    task_id_list = []
    for task_id in task_ids:
        task_id_list.extend([tid.strip() for tid in task_id.split(",")])

    # Process multiple task IDs
    updated_tasks = []
    failed_tasks = []
    repositories_to_update = set()

    for task_id in task_id_list:
        try:
            # Try to find task by ID or title
            result = find_task_by_title_or_id(manager, task_id, repo)

            # Handle the result manually for batch processing
            if result[0] is None:
                # Not found
                if len(task_id_list) > 1:
                    click.secho(f"✗ No task found matching '{task_id}'", fg="red")
                    failed_tasks.append(task_id)
                    continue
                else:
                    click.secho(f"Error: No task found matching '{task_id}'", fg="red", err=True)
                    ctx.exit(1)

            elif isinstance(result[0], list):
                # Multiple matches
                if len(task_id_list) > 1:
                    click.secho(f"✗ Multiple tasks found matching '{task_id}' - skipping", fg="red")
                    failed_tasks.append(task_id)
                    continue
                else:
                    # Let select_task_from_result handle the interactive selection
                    task, repository = select_task_from_result(ctx, result, task_id)
            else:
                # Single match found
                task, repository = result

            # Check if we're unarchiving a completed task (only for single task operations)
            was_completed = task.status == "completed"

            # Mark as cancelled
            task.status = "cancelled"
            repository.save_task(task)

            # Prompt for subtasks if unarchiving and processing single task
            if was_completed and len(task_id_list) == 1:
                prompt_for_subtask_unarchiving(manager, task, "cancelled", batch_mode=False)

            updated_tasks.append((task, repository))
            repositories_to_update.add(repository)

        except Exception as e:
            # Unexpected error - show message and continue with next task
            failed_tasks.append(task_id)
            if len(task_id_list) > 1:
                click.secho(f"✗ Could not mark task '{task_id}' as cancelled: {e}", fg="red")
            else:
                raise

    # Show summary
    if updated_tasks:
        click.echo()
        for task, _ in updated_tasks:
            click.secho(f"✓ Task marked as cancelled: {task}", fg="green")

        # Show summary for batch operations
        if len(task_id_list) > 1:
            click.echo()
            click.secho(f"Updated {len(updated_tasks)} of {len(task_id_list)} tasks", fg="green")

    # Update cache and display for affected repositories
    # For simplicity, just update the first repository or show all tasks
    if repositories_to_update:
        first_repo = list(repositories_to_update)[0]
        click.echo()
        update_cache_and_display_repo(manager, first_repo, config)
