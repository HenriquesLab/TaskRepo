"""Extend command for extending task due dates."""

from datetime import datetime, timedelta
from typing import Tuple

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.date_parser import format_date_input, parse_date_or_duration
from taskrepo.utils.helpers import find_task_by_title_or_id


@click.command(name="ext")
@click.argument("task_ids", nargs=-1, required=True)
@click.argument("date_or_duration")
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.pass_context
def ext(ctx, task_ids: Tuple[str, ...], date_or_duration, repo):
    """Set task due dates to a specific date or extend by a duration.

    Supports multiple tasks at once using space-separated or comma-separated IDs.

    For durations (1w, 2d, etc.): Extends from current due date, or sets from today if no due date.
    For dates (tomorrow, 2025-10-30, etc.): Sets due date to the specified date directly.

    TASK_IDS: Task ID(s) to modify (space or comma-separated for multiple)

    DATE_OR_DURATION: Target date or duration
        Durations: 1w, 2d, 3m, 1y
        Keywords: today, tomorrow, yesterday, next week, next month, next year
        Weekdays: next monday, this friday, monday
        ISO dates: 2025-10-30
        Natural dates: "Oct 30", "October 30 2025"

    Examples:
        tsk ext 4 tomorrow    # Set task 4 due date to tomorrow

        tsk ext 4 1w          # Extend task 4 by 1 week from current due date

        tsk ext 4 5 6 2d      # Extend tasks 4, 5, and 6 by 2 days (space-separated)

        tsk ext 4,5,6 2d      # Extend tasks 4, 5, and 6 by 2 days (comma-separated)

        tsk ext 10 "next week"  # Set task 10 due date to next week

        tsk ext 7 2025-11-15  # Set task 7 due date to Nov 15, 2025
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Parse date or duration
    try:
        parsed_value, is_absolute_date = parse_date_or_duration(date_or_duration)
    except ValueError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        ctx.exit(1)

    # Flatten comma-separated task IDs (supports both "4 5 6" and "4,5,6")
    task_id_list = []
    for task_id in task_ids:
        task_id_list.extend([tid.strip() for tid in task_id.split(",")])

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

        # Calculate new due date based on whether it's absolute or relative
        if is_absolute_date:
            # Set to specific date (ignoring current due date)
            assert isinstance(parsed_value, datetime)
            new_due = parsed_value
        else:
            # Extend by duration
            assert isinstance(parsed_value, timedelta)
            if task.due:
                # Extend from existing due date
                new_due = task.due + parsed_value
            else:
                # Extend from today at midnight
                now = datetime.now()
                today_midnight = datetime(now.year, now.month, now.day)
                new_due = today_midnight + parsed_value

        # Update task
        task.due = new_due
        task.modified = datetime.now()

        # Save task
        repository.save_task(task)

        # Display result
        action_verb = "Set" if is_absolute_date else "Extended"
        click.secho(f"✓ {action_verb} task: [{task.id[:8]}...] {task.title}", fg="green")
        click.echo(f"  Old due date: {old_due_str}")

        if is_absolute_date:
            click.echo(f"  Set to: {format_date_input(date_or_duration, parsed_value, is_absolute_date)}")
        else:
            click.echo(f"  Extension: {format_date_input(date_or_duration, parsed_value, is_absolute_date)}")

        click.echo(f"  New due date: {new_due.strftime('%Y-%m-%d')}")
        click.echo()

        # Track for summary table
        extended_tasks.append(task)
        extended_repos.append(repository)

    # Display summary
    if extended_tasks:
        total = len(task_id_list)
        success = len(extended_tasks)
        action_verb = "Updated" if is_absolute_date else "Extended"

        if failed_count > 0:
            click.secho(f"{action_verb} {success} of {total} tasks ({failed_count} failed).", fg="yellow")
        else:
            click.secho(f"{action_verb} {success} task{'s' if success != 1 else ''} successfully.", fg="green")

        click.echo()

        # Display updated tasks in table
        display_tasks_table(extended_tasks, config, save_cache=False)
    else:
        # All failed
        click.secho(f"Failed to update any tasks ({failed_count} errors).", fg="red")
        ctx.exit(1)
