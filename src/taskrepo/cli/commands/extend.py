"""Extend command for extending task due dates."""

from datetime import datetime

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.duration import format_duration, parse_duration
from taskrepo.utils.helpers import find_task_by_title_or_id


@click.command(name="ext")
@click.argument("task_ids")
@click.argument("duration")
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def ext(ctx, task_ids, duration, repo):
    """Extend task due dates by a specified duration.

    Supports extending multiple tasks at once using comma-separated IDs.
    If a task has no due date, sets it to today + duration.

    TASK_IDS: Task ID(s) to extend (comma-separated for multiple, e.g., "4,5,6")

    DURATION: Time to extend (e.g., "1w" for 1 week, "2d" for 2 days, "3m" for 3 months, "1y" for 1 year)

    Examples:
        tsk ext 4 1w          # Extend task 4 by 1 week

        tsk ext 4,5,6 2d      # Extend tasks 4, 5, and 6 by 2 days

        tsk ext 10 3m --repo work  # Extend task 10 by 3 months in work repo
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Parse duration
    try:
        duration_delta = parse_duration(duration)
    except ValueError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        ctx.exit(1)

    # Parse task IDs (comma-separated)
    task_id_list = [tid.strip() for tid in task_ids.split(",")]

    # Track results
    extended_tasks = []
    extended_repos = []
    failed_count = 0

    click.echo()  # Blank line before output

    # Process each task
    for task_id in task_id_list:
        # Find task
        result = find_task_by_title_or_id(manager, task_id, repo)

        if result[0] is None:
            # Not found
            click.secho(f"✗ Error: No task found matching '{task_id}'", fg="red")
            failed_count += 1
            continue

        elif isinstance(result[0], list):
            # Multiple matches - ask user to select
            click.echo(f"Multiple tasks found matching '{task_id}':")
            for idx, (t, r) in enumerate(zip(result[0], result[1], strict=False), start=1):
                click.echo(f"  {idx}. [{t.id[:8]}...] {t.title} (repo: {r.name})")

            try:
                choice = click.prompt("\nSelect task number", type=int)
                if choice < 1 or choice > len(result[0]):
                    click.secho("Invalid selection", fg="red")
                    failed_count += 1
                    continue
                task = result[0][choice - 1]
                repository = result[1][choice - 1]
            except (ValueError, click.Abort):
                click.echo("Cancelled.")
                failed_count += 1
                continue
        else:
            # Single match found
            task, repository = result

        # Store old due date for display
        old_due = task.due
        old_due_str = old_due.strftime("%Y-%m-%d") if old_due else "None"

        # Calculate new due date
        if task.due:
            # Extend existing due date
            new_due = task.due + duration_delta
            was_set = False
        else:
            # Set new due date from today
            new_due = datetime.now() + duration_delta
            was_set = True

        # Update task
        task.due = new_due
        task.modified = datetime.now()

        # Save task
        repository.save_task(task)

        # Display result
        click.secho(f"✓ Extended task: [{task.id[:8]}...] {task.title}", fg="green")
        click.echo(f"  Old due date: {old_due_str}")
        click.echo(f"  Extension: {format_duration(duration)}")
        new_due_suffix = " (set from today)" if was_set else ""
        click.echo(f"  New due date: {new_due.strftime('%Y-%m-%d')}{new_due_suffix}")
        click.echo()

        # Track for summary table
        extended_tasks.append(task)
        extended_repos.append(repository)

    # Display summary
    if extended_tasks:
        total = len(task_id_list)
        success = len(extended_tasks)

        if failed_count > 0:
            click.secho(f"Extended {success} of {total} tasks ({failed_count} failed).", fg="yellow")
        else:
            click.secho(f"Extended {success} task{'s' if success != 1 else ''} successfully.", fg="green")

        click.echo()

        # Display updated tasks in table
        display_tasks_table(extended_tasks, config, save_cache=False)
    else:
        # All failed
        click.secho(f"Failed to extend any tasks ({failed_count} errors).", fg="red")
        ctx.exit(1)
