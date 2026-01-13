"""Update command for modifying task fields."""

from typing import Optional, Tuple

import click
from dateparser import parse as parse_date

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result


@click.command()
@click.argument("task_ids", nargs=-1, required=True)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.option("--priority", "-p", type=click.Choice(["H", "M", "L"]), help="Set priority")
@click.option(
    "--status", "-s", type=click.Choice(["pending", "in-progress", "completed", "cancelled"]), help="Set status"
)
@click.option("--project", help="Set project name")
@click.option("--add-tag", multiple=True, help="Add tag(s) to task")
@click.option("--remove-tag", multiple=True, help="Remove tag(s) from task")
@click.option("--add-assignee", multiple=True, help="Add assignee(s) to task (use @username format)")
@click.option("--remove-assignee", multiple=True, help="Remove assignee(s) from task")
@click.option("--due", help="Set due date (natural language or ISO format)")
@click.option("--title", help="Set new title")
@click.pass_context
def update(
    ctx,
    task_ids: Tuple[str, ...],
    repo: Optional[str],
    priority: Optional[str],
    status: Optional[str],
    project: Optional[str],
    add_tag: Tuple[str, ...],
    remove_tag: Tuple[str, ...],
    add_assignee: Tuple[str, ...],
    remove_assignee: Tuple[str, ...],
    due: Optional[str],
    title: Optional[str],
):
    """Update fields for one or more tasks.

    Examples:
        # Update single task
        tsk update 5 --priority H --add-tag urgent

        # Update multiple tasks
        tsk update 5,6,7 --status in-progress --add-assignee @alice

        # Update with various fields
        tsk update 10 --priority M --project backend --due tomorrow

    TASK_IDS: One or more task IDs (comma-separated or space-separated)
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Check that at least one update option is provided
    if not any([priority, status, project, add_tag, remove_tag, add_assignee, remove_assignee, due, title]):
        click.secho("Error: At least one update option must be specified", fg="red", err=True)
        ctx.exit(1)

    # Flatten comma-separated task IDs
    task_id_list = []
    for task_id in task_ids:
        task_id_list.extend([tid.strip() for tid in task_id.split(",")])

    updated_count = 0

    for task_id in task_id_list:
        # Find task
        result = find_task_by_title_or_id(manager, task_id, repo)

        if result[0] is None:
            click.secho(f"✗ No task found matching '{task_id}'", fg="red")
            continue

        task, repository = select_task_from_result(ctx, result, task_id)

        # Apply updates
        changes = []

        if priority:
            task.priority = priority
            changes.append(f"priority → {priority}")

        if status:
            task.status = status
            changes.append(f"status → {status}")

        if project:
            task.project = project
            changes.append(f"project → {project}")

        if title:
            task.title = title
            changes.append(f"title → {title}")

        if add_tag:
            if task.tags is None:
                task.tags = []
            for tag in add_tag:
                if tag not in task.tags:
                    task.tags.append(tag)
                    changes.append(f"+tag: {tag}")

        if remove_tag:
            if task.tags:
                for tag in remove_tag:
                    if tag in task.tags:
                        task.tags.remove(tag)
                        changes.append(f"-tag: {tag}")

        if add_assignee:
            if task.assignees is None:
                task.assignees = []
            for assignee in add_assignee:
                # Ensure @ prefix
                if not assignee.startswith("@"):
                    assignee = "@" + assignee
                if assignee not in task.assignees:
                    task.assignees.append(assignee)
                    changes.append(f"+assignee: {assignee}")

        if remove_assignee:
            if task.assignees:
                for assignee in remove_assignee:
                    # Handle with or without @ prefix
                    if not assignee.startswith("@"):
                        assignee = "@" + assignee
                    if assignee in task.assignees:
                        task.assignees.remove(assignee)
                        changes.append(f"-assignee: {assignee}")

        if due:
            parsed_date = parse_date(due)
            if parsed_date:
                task.due = parsed_date
                changes.append(f"due → {due}")
            else:
                click.secho(f"Warning: Could not parse due date '{due}' for task {task_id}", fg="yellow")

        # Save task
        if changes:
            repository.save_task(task)
            updated_count += 1
            click.secho(f"✓ Updated task: {task.title}", fg="green")
            for change in changes:
                click.echo(f"  • {change}")

    click.echo()
    if updated_count > 0:
        click.secho(f"Updated {updated_count} task(s)", fg="green", bold=True)
    else:
        click.secho("No tasks were updated", fg="yellow")
