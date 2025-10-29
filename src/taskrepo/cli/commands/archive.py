"""Archive command for moving tasks to archive folder."""

import click
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.validation import Validator

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.display_constants import STATUS_EMOJIS
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result
from taskrepo.utils.id_mapping import get_cache_size


@click.command()
@click.argument("task_ids", nargs=-1)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def archive(ctx, task_ids, repo):
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
            archived_tasks = repository.list_archived_tasks()
        else:
            # Get archived tasks from all repos
            archived_tasks = []
            for r in manager.discover_repositories():
                archived_tasks.extend(r.list_archived_tasks())

        if not archived_tasks:
            repo_msg = f" in repository '{repo}'" if repo else ""
            click.echo(f"No archived tasks found{repo_msg}.")
            return

        # Get the number of active tasks from cache to use as offset
        active_task_count = get_cache_size()

        # Display archived tasks with IDs starting after active tasks
        display_tasks_table(
            archived_tasks,
            config,
            title=f"Archived Tasks ({len(archived_tasks)} found)",
            save_cache=False,
            id_offset=active_task_count,
        )
        return

    # Process multiple task IDs
    archived_tasks = []
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

            # Check for subtasks and prompt (only for single task operations)
            if len(task_ids) == 1:
                subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)

                if subtasks_with_repos:
                    count = len(subtasks_with_repos)
                    subtask_word = "subtask" if count == 1 else "subtasks"

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

                    if response in ["y", "yes"]:
                        # Archive all subtasks
                        archived_count = 0
                        for subtask, subtask_repo in subtasks_with_repos:
                            if subtask_repo.archive_task(subtask.id):
                                archived_count += 1

                        if archived_count > 0:
                            click.secho(f"✓ Archived {archived_count} {subtask_word}", fg="green")

            # Archive the task
            success = repository.archive_task(task.id)

            if success:
                archived_tasks.append((task, repository))
                repositories_to_update.add(repository)
            else:
                failed_tasks.append(task_id)
                if len(task_ids) > 1:
                    click.secho(f"✗ Could not archive task '{task_id}'", fg="red")
                else:
                    click.secho(f"Error: Could not archive task '{task_id}'", fg="red", err=True)
                    ctx.exit(1)

        except Exception as e:
            # Unexpected error - show message and continue with next task
            failed_tasks.append(task_id)
            if len(task_ids) > 1:
                click.secho(f"✗ Could not archive task '{task_id}': {e}", fg="red")
            else:
                raise

    # Show summary
    if archived_tasks:
        click.echo()
        for task, _ in archived_tasks:
            click.secho(f"✓ Task archived: {task}", fg="green")

        # Show summary for batch operations
        if len(task_ids) > 1:
            click.echo()
            click.secho(f"Archived {len(archived_tasks)} of {len(task_ids)} tasks", fg="green")

    # Update cache and display archived tasks from all repos
    if repositories_to_update:
        from taskrepo.utils.id_mapping import save_id_cache
        from taskrepo.utils.sorting import sort_tasks

        # Update cache with ALL non-archived tasks across all repos (sorted)
        # Use stable mode (rebalance=False) to preserve IDs
        all_tasks_all_repos = manager.list_all_tasks(include_archived=False)
        sorted_tasks = sort_tasks(all_tasks_all_repos, config)
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
