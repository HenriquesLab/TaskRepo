"""Done command for marking tasks as completed."""

import click
from prompt_toolkit.shortcuts import confirm

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.display_constants import STATUS_EMOJIS
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result, update_cache_and_display_repo
from taskrepo.utils.id_mapping import get_cache_size


@click.command()
@click.argument("task_id", required=False)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def done(ctx, task_id, repo):
    """Mark a task as completed, or list completed tasks if no task ID is provided.

    TASK_ID: Task ID to mark as done (optional - if omitted, lists completed tasks)
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # If no task_id provided, list completed tasks
    if task_id is None:
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

    # Try to find task by ID or title
    result = find_task_by_title_or_id(manager, task_id, repo)
    task, repository = select_task_from_result(ctx, result, task_id)

    # Check for subtasks and prompt user
    subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)

    if subtasks_with_repos:
        # Show subtask count and prompt
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

    click.secho(f"✓ Task marked as completed: {task}", fg="green")
    click.echo()

    # Update cache and display repository tasks
    update_cache_and_display_repo(manager, repository, config)
