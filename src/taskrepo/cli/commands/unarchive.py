"""Unarchive command for restoring archived tasks."""

import click
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.validation import Validator

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils.display_constants import STATUS_EMOJIS
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result


@click.command()
@click.argument("task_ids", nargs=-1, required=True)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.option("--yes", "-y", is_flag=True, help="Automatically unarchive subtasks (skip prompt)")
@click.pass_context
def unarchive(ctx, task_ids, repo, yes):
    """Unarchive one or more tasks (restore from archive folder).

    TASK_IDS: One or more task IDs to unarchive
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Process multiple task IDs
    unarchived_tasks = []
    failed_tasks = []
    repositories_to_update = set()

    for task_id in task_ids:
        try:
            # Try to find task by ID or title (in archive)
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

            # Check for archived subtasks and prompt (only for single task operations)
            if len(task_ids) == 1:
                subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)

                # Filter to only archived subtasks
                archived_subtasks = []
                for subtask, subtask_repo in subtasks_with_repos:
                    # Check if subtask is in archive folder
                    archive_file = subtask_repo.archive_dir / f"task-{subtask.id}.md"
                    if archive_file.exists():
                        archived_subtasks.append((subtask, subtask_repo))

                if archived_subtasks:
                    count = len(archived_subtasks)
                    subtask_word = "subtask" if count == 1 else "subtasks"

                    # Determine whether to unarchive subtasks
                    unarchive_subtasks = yes  # Default to --yes flag value

                    if not yes:
                        # Show subtasks and prompt
                        click.echo(f"\nThis task has {count} archived {subtask_word}:")
                        for subtask, subtask_repo in archived_subtasks:
                            status_emoji = STATUS_EMOJIS.get(subtask.status, "")
                            click.echo(f"  • {status_emoji} {subtask.title} (repo: {subtask_repo.name})")

                        # Prompt for confirmation with Y as default
                        yn_validator = Validator.from_callable(
                            lambda text: text.lower() in ["y", "n", "yes", "no"],
                            error_message="Please enter 'y' or 'n'",
                            move_cursor_to_end=True,
                        )

                        response = prompt(
                            f"Unarchive all {count} {subtask_word} too? (Y/n) ",
                            default="y",
                            validator=yn_validator,
                        ).lower()

                        unarchive_subtasks = response in ["y", "yes"]

                    if unarchive_subtasks:
                        # Unarchive all subtasks
                        unarchived_count = 0
                        for subtask, subtask_repo in archived_subtasks:
                            if subtask_repo.unarchive_task(subtask.id):
                                unarchived_count += 1

                        if unarchived_count > 0:
                            click.secho(f"✓ Unarchived {unarchived_count} {subtask_word}", fg="green")

            # Unarchive the task
            success = repository.unarchive_task(task.id)

            if success:
                unarchived_tasks.append((task, repository))
                repositories_to_update.add(repository)
            else:
                failed_tasks.append(task_id)
                if len(task_ids) > 1:
                    click.secho(f"✗ Could not unarchive task '{task_id}'", fg="red")
                else:
                    click.secho(f"Error: Could not unarchive task '{task_id}'", fg="red", err=True)
                    ctx.exit(1)

        except Exception as e:
            # Unexpected error - show message and continue with next task
            failed_tasks.append(task_id)
            if len(task_ids) > 1:
                click.secho(f"✗ Could not unarchive task '{task_id}': {e}", fg="red")
            else:
                raise

    # Show summary
    if unarchived_tasks:
        click.echo()
        for task, _ in unarchived_tasks:
            click.secho(f"✓ Task unarchived: {task}", fg="green")

        # Show summary for batch operations
        if len(task_ids) > 1:
            click.echo()
            click.secho(f"Unarchived {len(unarchived_tasks)} of {len(task_ids)} tasks", fg="green")

    # Display tasks from the first updated repository
    if repositories_to_update:
        from taskrepo.utils.helpers import update_cache_and_display_repo

        first_repo = list(repositories_to_update)[0]
        click.echo()
        update_cache_and_display_repo(manager, first_repo, config)
