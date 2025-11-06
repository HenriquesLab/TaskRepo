"""Done command for marking tasks as completed."""

from typing import Tuple

import click
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.validation import Validator

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.display_constants import STATUS_EMOJIS
from taskrepo.utils.helpers import process_tasks_batch, update_cache_and_display_repo


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
        completed_tasks_list = [t for t in tasks if t.status == "completed"]

        if not completed_tasks_list:
            repo_msg = f" in repository '{repo}'" if repo else ""
            click.echo(f"No completed tasks found{repo_msg}.")
            return

        # Display completed tasks (they're part of regular task list now)
        display_tasks_table(
            completed_tasks_list,
            config,
            title=f"Completed Tasks ({len(completed_tasks_list)} found)",
            save_cache=False,
            show_completed_date=True,
        )
        return

    def mark_as_completed(task, repository):
        """Handler to mark task as completed."""
        # Mark as completed
        task.status = "completed"
        repository.save_task(task)
        return True, None

    # Use batch processor
    completed_tasks, failed_tasks = process_tasks_batch(
        ctx, manager, task_ids, repo, task_handler=mark_as_completed, operation_name="completed"
    )

    # Handle subtask prompting for single task
    if len(completed_tasks) == 1 and len(task_ids) == 1:
        task, _ = completed_tasks[0]
        subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)

        if subtasks_with_repos:
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

    # Show individual success messages
    if completed_tasks:
        click.echo()
        for task, _ in completed_tasks:
            click.secho(f"✓ Task marked as completed: {task}", fg="green")

    # Update cache and display for affected repositories
    if completed_tasks:
        repositories_to_update = {repo for _, repo in completed_tasks}
        first_repo = list(repositories_to_update)[0]
        click.echo()
        update_cache_and_display_repo(manager, first_repo, config)
