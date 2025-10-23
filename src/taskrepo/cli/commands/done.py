"""Done command for marking tasks as completed."""

import click
from prompt_toolkit.shortcuts import confirm

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.display_constants import STATUS_EMOJIS
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result, update_cache_and_display_repo
from taskrepo.utils.id_mapping import get_cache_size


@click.command()
@click.argument("task_ids", nargs=-1)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def done(ctx, task_ids, repo):
    """Mark one or more tasks as completed, or list completed tasks if no task IDs are provided.

    TASK_IDS: One or more task IDs to mark as done (optional - if omitted, lists completed tasks)
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # If no task_ids provided, list completed tasks
    if not task_ids:
        # Get tasks from specified repo or all repos
        # Load from both tasks/ and tasks/done/ folders
        if repo:
            repository = manager.get_repository(repo)
            if not repository:
                click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
                ctx.exit(1)
            tasks = repository.list_tasks(include_completed=True)
        else:
            tasks = manager.list_all_tasks(include_completed=True)

        # Filter to only completed tasks
        completed_tasks = [t for t in tasks if t.status == "completed"]

        if not completed_tasks:
            repo_msg = f" in repository '{repo}'" if repo else ""
            click.echo(f"No completed tasks found{repo_msg}.")
            return

        # Get the number of active tasks from cache to use as offset
        active_task_count = get_cache_size()

        # Display completed tasks with IDs starting after active tasks
        display_tasks_table(
            completed_tasks,
            config,
            title=f"Completed Tasks ({len(completed_tasks)} found)",
            save_cache=False,
            id_offset=active_task_count,
            show_completed_date=True,
        )
        return

    # Process multiple task IDs
    completed_tasks = []
    failed_tasks = []
    repositories_to_update = set()

    for task_id in task_ids:
        try:
            # Try to find task by ID or title
            result = find_task_by_title_or_id(manager, task_id, repo)

            # Handle the result manually for batch processing
            if result[0] is None:
                # Not found
                if len(task_ids) > 1:
                    click.secho(f"✗ No task found matching '{task_id}'", fg="red")
                    failed_tasks.append(task_id)
                    continue
                else:
                    click.secho(f"Error: No task found matching '{task_id}'", fg="red", err=True)
                    ctx.exit(1)

            elif isinstance(result[0], list):
                # Multiple matches
                if len(task_ids) > 1:
                    click.secho(f"✗ Multiple tasks found matching '{task_id}' - skipping", fg="red")
                    failed_tasks.append(task_id)
                    continue
                else:
                    # Let select_task_from_result handle the interactive selection
                    task, repository = select_task_from_result(ctx, result, task_id)
            else:
                # Single match found
                task, repository = result

            # For batch operations, check for subtasks but don't prompt
            # Just mark the parent task as completed
            subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)

            if subtasks_with_repos and len(task_ids) == 1:
                # Only prompt for subtasks if processing a single task
                count = len(subtasks_with_repos)
                subtask_word = "subtask" if count == 1 else "subtasks"

                click.echo(f"\nThis task has {count} {subtask_word}:")
                for subtask, subtask_repo in subtasks_with_repos:
                    status_emoji = STATUS_EMOJIS.get(subtask.status, "")
                    click.echo(f"  • {status_emoji} {subtask.title} (repo: {subtask_repo.name})")

                # Prompt for confirmation
                if confirm(f"Mark all {count} {subtask_word} as completed too?"):
                    # Mark all subtasks as completed
                    completed_count = 0
                    for subtask, subtask_repo in subtasks_with_repos:
                        if subtask.status != "completed":  # Only if not already completed
                            subtask.status = "completed"
                            subtask_repo.save_task(subtask)
                            completed_count += 1

                    if completed_count > 0:
                        click.secho(f"✓ Marked {completed_count} {subtask_word} as completed", fg="green")

            # Mark as completed
            task.status = "completed"
            repository.save_task(task)

            completed_tasks.append((task, repository))
            repositories_to_update.add(repository)

        except Exception as e:
            # Unexpected error - show message and continue with next task
            failed_tasks.append(task_id)
            if len(task_ids) > 1:
                click.secho(f"✗ Could not mark task '{task_id}' as completed: {e}", fg="red")
            else:
                raise

    # Show summary
    if completed_tasks:
        click.echo()
        for task, _ in completed_tasks:
            click.secho(f"✓ Task marked as completed: {task}", fg="green")

        # Show summary for batch operations
        if len(task_ids) > 1:
            click.echo()
            click.secho(f"Completed {len(completed_tasks)} of {len(task_ids)} tasks", fg="green")

    # Update cache and display for affected repositories
    # For simplicity, just update the first repository or show all tasks
    if repositories_to_update:
        first_repo = list(repositories_to_update)[0]
        click.echo()
        update_cache_and_display_repo(manager, first_repo, config)
