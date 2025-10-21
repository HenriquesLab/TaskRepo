"""Done command for marking tasks as completed."""

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.helpers import find_task_by_title_or_id


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
        if repo:
            repository = manager.get_repository(repo)
            if not repository:
                click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
                ctx.exit(1)
            tasks = repository.list_tasks()
        else:
            tasks = manager.list_all_tasks()

        # Filter to only completed tasks
        completed_tasks = [t for t in tasks if t.status == "completed"]

        if not completed_tasks:
            repo_msg = f" in repository '{repo}'" if repo else ""
            click.echo(f"No completed tasks found{repo_msg}.")
            return

        # Display completed tasks
        display_tasks_table(completed_tasks, config, title=f"Completed Tasks ({len(completed_tasks)} found)")
        return

    # Try to find task by ID or title
    result = find_task_by_title_or_id(manager, task_id, repo)

    if result[0] is None:
        # Not found
        click.secho(f"Error: No task found matching '{task_id}'", fg="red", err=True)
        ctx.exit(1)
    elif isinstance(result[0], list):
        # Multiple matches - ask user to select
        click.echo(f"\nMultiple tasks found matching '{task_id}':")
        for idx, (t, r) in enumerate(zip(result[0], result[1], strict=False), start=1):
            click.echo(f"  {idx}. [{t.id[:8]}...] {t.title} (repo: {r.name})")

        try:
            choice = click.prompt("\nSelect task number", type=int)
            if choice < 1 or choice > len(result[0]):
                click.secho("Invalid selection", fg="red", err=True)
                ctx.exit(1)
            task = result[0][choice - 1]
            repository = result[1][choice - 1]
        except (ValueError, click.Abort):
            click.echo("Cancelled.")
            ctx.exit(0)
    else:
        # Single match found
        task, repository = result

    # Check for subtasks and prompt user
    subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)

    if subtasks_with_repos:
        # Show subtask count and prompt
        count = len(subtasks_with_repos)
        subtask_word = "subtask" if count == 1 else "subtasks"

        click.echo(f"\nThis task has {count} {subtask_word}:")
        for subtask, subtask_repo in subtasks_with_repos:
            status_emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}.get(subtask.status, "")
            click.echo(f"  • {status_emoji} {subtask.title} (repo: {subtask_repo.name})")

        # Prompt for confirmation
        if click.confirm(f"\nMark all {count} {subtask_word} as completed too?", default=True):
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

    # Display all tasks in the repository
    all_tasks = repository.list_tasks()
    # Filter out completed tasks (consistent with default list behavior)
    active_tasks = [t for t in all_tasks if t.status != "completed"]

    if active_tasks:
        display_tasks_table(active_tasks, config)
