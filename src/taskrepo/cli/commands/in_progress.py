"""In Progress command for marking tasks as in progress."""

from typing import Tuple

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils.helpers import (
    process_tasks_batch,
    prompt_for_subtask_unarchiving,
    update_cache_and_display_repo,
)


@click.command()
@click.argument("task_ids", nargs=-1, required=True)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def in_progress(ctx, task_ids: Tuple[str, ...], repo):
    """Mark one or more tasks as in progress.

    TASK_IDS: One or more task IDs to mark as in progress (comma-separated)
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Track which tasks were completed (for subtask handling)
    was_completed_map = {}

    def mark_as_in_progress(task, repository):
        """Handler to mark task as in progress."""
        # Store completion status before changing
        was_completed_map[task.id] = task.status == "completed"

        # Mark as in progress
        task.status = "in-progress"
        repository.save_task(task)
        return True, None

    # Use batch processor
    updated_tasks, failed_tasks = process_tasks_batch(
        ctx, manager, task_ids, repo, task_handler=mark_as_in_progress, operation_name="updated"
    )

    # Handle subtask prompting for single task that was completed
    if len(updated_tasks) == 1 and len(task_ids) == 1:
        task, _ = updated_tasks[0]
        if was_completed_map.get(task.id, False):
            prompt_for_subtask_unarchiving(manager, task, "in-progress", batch_mode=False)

    # Show individual success messages
    if updated_tasks:
        click.echo()
        for task, _ in updated_tasks:
            click.secho(f"✓ Task marked as in progress: {task}", fg="green")

    # Update cache and display for affected repositories
    if updated_tasks:
        repositories_to_update = {repo for _, repo in updated_tasks}
        first_repo = list(repositories_to_update)[0]
        click.echo()
        update_cache_and_display_repo(manager, first_repo, config)
