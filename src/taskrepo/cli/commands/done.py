"""Done command for marking tasks as completed."""

from typing import Tuple

import click
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.validation import Validator

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.display_constants import STATUS_EMOJIS
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result, update_cache_and_display_repo


@click.command()
@click.argument("task_ids", nargs=-1)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.option("--yes", "-y", is_flag=True, help="Automatically mark subtasks as completed (skip prompt)")
@click.pass_context
def done(ctx, task_ids: Tuple[str, ...], repo, yes):
    """Mark one or more tasks as completed, or list completed tasks if no task IDs are provided.

    Supports multiple tasks at once using space-separated or comma-separated IDs.

    Examples:
        tsk done 4              # Mark task 4 as completed
        tsk done 4 5 6          # Mark tasks 4, 5, and 6 as completed (space-separated)
        tsk done 4,5,6          # Mark tasks 4, 5, and 6 as completed (comma-separated)

    TASK_IDS: One or more task IDs to mark as done (optional - if omitted, lists completed tasks)
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # If no task_ids provided, list completed tasks
    if not task_ids:
        # Get tasks from specified repo or all repos (excluding archived)
        if repo:
            repository = manager.get_repository(repo)
            if not repository:
                click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
                ctx.exit(1)
            tasks = repository.list_tasks(include_archived=False)
        else:
            tasks = manager.list_all_tasks(include_archived=False)

        # Filter to only completed tasks
        completed_tasks = [t for t in tasks if t.status == "completed"]

        if not completed_tasks:
            repo_msg = f" in repository '{repo}'" if repo else ""
            click.echo(f"No completed tasks found{repo_msg}.")
            return

        # Display completed tasks (they're part of regular task list now)
        display_tasks_table(
            completed_tasks,
            config,
            title=f"Completed Tasks ({len(completed_tasks)} found)",
            save_cache=False,
            show_completed_date=True,
        )
        return

    # Flatten comma-separated task IDs (supports both "4 5 6" and "4,5,6")
    task_id_list = []
    for task_id in task_ids:
        task_id_list.extend([tid.strip() for tid in task_id.split(",")])

    # Process multiple task IDs
    completed_tasks = []
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

            # For batch operations, check for subtasks but don't prompt
            # Just mark the parent task as completed
            subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)

            if subtasks_with_repos and len(task_id_list) == 1:
                # Only prompt for subtasks if processing a single task
                count = len(subtasks_with_repos)
                subtask_word = "subtask" if count == 1 else "subtasks"

                # Determine whether to mark subtasks
                mark_subtasks = yes  # Default to --yes flag value

                if not yes:
                    # Show subtasks and prompt
                    click.echo(f"\nThis task has {count} {subtask_word}:")
                    for subtask, subtask_repo in subtasks_with_repos:
                        status_emoji = STATUS_EMOJIS.get(subtask.status, "")
                        click.echo(f"  • {status_emoji} {subtask.title} (repo: {subtask_repo.name})")

                    # Prompt for confirmation with Y as default
                    yn_validator = Validator.from_callable(
                        lambda text: text.lower() in ["y", "n", "yes", "no"],
                        error_message="Please enter 'y' or 'n'",
                        move_cursor_to_end=True,
                    )

                    response = prompt(
                        f"Mark all {count} {subtask_word} as completed too? (Y/n) ",
                        default="y",
                        validator=yn_validator,
                    ).lower()

                    mark_subtasks = response in ["y", "yes"]

                if mark_subtasks:
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
            if len(task_id_list) > 1:
                click.secho(f"✗ Could not mark task '{task_id}' as completed: {e}", fg="red")
            else:
                click.secho(f"Error: Could not mark task '{task_id}' as completed: {e}", fg="red", err=True)
                ctx.exit(1)

    # Show summary
    if completed_tasks:
        click.echo()
        for task, _ in completed_tasks:
            click.secho(f"✓ Task marked as completed: {task}", fg="green")

        # Show summary for batch operations
        if len(task_id_list) > 1:
            click.echo()
            click.secho(f"Completed {len(completed_tasks)} of {len(task_id_list)} tasks", fg="green")

    # Update cache and display for affected repositories
    # For simplicity, just update the first repository or show all tasks
    if repositories_to_update:
        first_repo = list(repositories_to_update)[0]
        click.echo()
        update_cache_and_display_repo(manager, first_repo, config)
