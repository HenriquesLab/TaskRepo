"""Archive command for moving tasks to archive folder."""

import sys
from typing import Tuple

import click
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.validation import Validator

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.display_constants import STATUS_EMOJIS
from taskrepo.utils.helpers import process_tasks_batch
from taskrepo.utils.id_mapping import get_cache_size


@click.command()
@click.argument("task_ids", nargs=-1)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.option("--yes", "-y", is_flag=True, help="Automatically archive subtasks (skip prompt)")
@click.pass_context
def archive(ctx, task_ids: Tuple[str, ...], repo, yes):
    """Archive one or more tasks, or list archived tasks if no task IDs are provided.

    TASK_IDS: One or more task IDs to archive (optional - if omitted, lists archived tasks)
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # If no task_ids provided, list archived tasks
    if not task_ids:
        # Get archived tasks from specified repo or all repos
        if repo:
            repository = manager.get_repository(repo)
            if not repository:
                click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
                ctx.exit(1)
            archived_tasks_list = repository.list_archived_tasks()
        else:
            # Get archived tasks from all repos
            archived_tasks_list = []
            for r in manager.discover_repositories():
                archived_tasks_list.extend(r.list_archived_tasks())

        if not archived_tasks_list:
            repo_msg = f" in repository '{repo}'" if repo else ""
            click.echo(f"No archived tasks found{repo_msg}.")
            return

        # Get the number of active tasks from cache to use as offset
        active_task_count = get_cache_size()

        # Display archived tasks with IDs starting after active tasks
        display_tasks_table(
            archived_tasks_list,
            config,
            title=f"Archived Tasks ({len(archived_tasks_list)} found)",
            save_cache=False,
            id_offset=active_task_count,
        )
        return

    def archive_task_handler(task, repository):
        """Handler to archive a task."""
        success = repository.archive_task(task.id)
        if success:
            return True, None
        else:
            return False, f"Could not archive task '{task.id}'"

    # Use batch processor
    archived_tasks, failed_tasks = process_tasks_batch(
        ctx, manager, task_ids, repo, task_handler=archive_task_handler, operation_name="archived"
    )

    # Handle subtask prompting for single task
    if len(archived_tasks) == 1 and len(task_ids) == 1:
        task, _ = archived_tasks[0]
        subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)

        if subtasks_with_repos:
            count = len(subtasks_with_repos)
            subtask_word = "subtask" if count == 1 else "subtasks"

            # Determine whether to archive subtasks
            archive_subtasks = yes  # Default to --yes flag value

            if not yes:
                # Check if we're in a terminal - if not, default to yes
                if not sys.stdin.isatty():
                    archive_subtasks = True
                else:
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
                        f"Archive all {count} {subtask_word} too? (Y/n) ",
                        default="y",
                        validator=yn_validator,
                    ).lower()

                    archive_subtasks = response in ["y", "yes"]

            if archive_subtasks:
                # Archive all subtasks
                archived_count = 0
                for subtask, subtask_repo in subtasks_with_repos:
                    if subtask_repo.archive_task(subtask.id):
                        archived_count += 1

                if archived_count > 0:
                    click.secho(f"✓ Archived {archived_count} {subtask_word}", fg="green")

    # Show individual success messages
    if archived_tasks:
        click.echo()
        for task, _ in archived_tasks:
            click.secho(f"✓ Task archived: {task}", fg="green")

    # Update cache and display archived tasks from all repos
    if archived_tasks:
        from taskrepo.utils.id_mapping import save_id_cache
        from taskrepo.utils.sorting import sort_tasks

        # Update cache with ALL non-archived tasks across all repos (sorted)
        # Use stable mode (rebalance=False) to preserve IDs
        all_tasks_all_repos = manager.list_all_tasks(include_archived=False)
        sorted_tasks = sort_tasks(all_tasks_all_repos, config, all_tasks=all_tasks_all_repos)
        save_id_cache(sorted_tasks, rebalance=False)

        # Get archived tasks from all repos
        archived_tasks_all_repos = []
        for r in manager.discover_repositories():
            archived_tasks_all_repos.extend(r.list_archived_tasks())

        if archived_tasks_all_repos:
            # Get the number of active tasks from cache to use as offset
            active_task_count = get_cache_size()

            # Display archived tasks with IDs starting after active tasks
            click.echo()
            display_tasks_table(
                archived_tasks_all_repos,
                config,
                title=f"Archived Tasks ({len(archived_tasks_all_repos)} found)",
                save_cache=False,
                id_offset=active_task_count,
            )
        else:
            click.echo()
            click.echo("No archived tasks.")
