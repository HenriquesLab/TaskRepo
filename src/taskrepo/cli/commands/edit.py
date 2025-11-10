"""Edit command for modifying existing tasks."""

import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Tuple

import click
import dateparser

from taskrepo.core.repository import RepositoryManager
from taskrepo.core.task import Task
from taskrepo.utils.helpers import (
    find_task_by_title_or_id,
    prompt_for_subtask_archiving,
    prompt_for_subtask_unarchiving,
    select_task_from_result,
    update_cache_and_display_repo,
)


def parse_list_field(value: str) -> list[str]:
    """Parse comma-separated values into a list.

    Args:
        value: Comma-separated string

    Returns:
        List of stripped values
    """
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def add_to_list_field(current: list[str], additions: list[str]) -> list[str]:
    """Add items to a list field, avoiding duplicates.

    Args:
        current: Current list of items
        additions: Items to add

    Returns:
        Updated list with additions
    """
    result = current.copy()
    for item in additions:
        if item not in result:
            result.append(item)
    return result


def remove_from_list_field(current: list[str], removals: list[str]) -> list[str]:
    """Remove items from a list field.

    Args:
        current: Current list of items
        removals: Items to remove

    Returns:
        Updated list with items removed
    """
    return [item for item in current if item not in removals]


def show_change_summary(changes: dict):
    """Display a summary of changes made to the task.

    Args:
        changes: Dictionary of field names to (old_value, new_value) tuples
    """
    if not changes:
        click.secho("No changes detected", fg="yellow")
        return

    click.echo()
    click.secho("Changes applied:", fg="cyan", bold=True)
    for field, (old_val, new_val) in changes.items():
        # Format values for display
        if isinstance(old_val, list):
            old_str = ", ".join(old_val) if old_val else "(empty)"
            new_str = ", ".join(new_val) if new_val else "(empty)"
        elif isinstance(old_val, datetime):
            old_str = old_val.strftime("%Y-%m-%d") if old_val else "(none)"
            new_str = new_val.strftime("%Y-%m-%d") if new_val else "(none)"
        else:
            old_str = str(old_val) if old_val else "(none)"
            new_str = str(new_val) if new_val else "(none)"

        click.echo(f"  {field}: {old_str} → {new_str}")


def _edit_task_interactive(task: Task, repository) -> bool:
    """Edit a task interactively with field-by-field prompts.

    Args:
        task: Task object to edit
        repository: Repository containing the task

    Returns:
        True if task was modified, False otherwise
    """
    from taskrepo.tui import prompts

    changes = {}

    while True:
        # Show field selection menu
        field = prompts.prompt_field_selection(task)

        if field is None:
            # User cancelled
            return False
        elif field == "done":
            # User finished editing
            break
        elif field == "all":
            # Edit all fields
            fields_to_edit = [
                "title",
                "status",
                "priority",
                "project",
                "assignees",
                "tags",
                "links",
                "due",
                "parent",
                "depends",
                "description",
            ]
        else:
            fields_to_edit = [field]

        # Prompt for each selected field
        for field_name in fields_to_edit:
            old_value = getattr(task, field_name)

            if field_name == "title":
                new_value = prompts.prompt_title(default=task.title)
                if new_value and new_value != old_value:
                    task.title = new_value
                    changes["title"] = (old_value, new_value)

            elif field_name == "status":
                new_value = prompts.prompt_status(default=task.status)
                if new_value != old_value:
                    task.status = new_value
                    changes["status"] = (old_value, new_value)

            elif field_name == "priority":
                new_value = prompts.prompt_priority(default=task.priority)
                if new_value != old_value:
                    task.priority = new_value
                    changes["priority"] = (old_value, new_value)

            elif field_name == "project":
                new_value = prompts.prompt_project(repository.get_projects(), default=task.project)
                if new_value != old_value:
                    task.project = new_value
                    changes["project"] = (old_value, new_value)

            elif field_name == "assignees":
                new_value = prompts.prompt_assignees(repository.get_assignees(), default=task.assignees)
                if new_value != old_value:
                    task.assignees = new_value
                    changes["assignees"] = (old_value, new_value)

            elif field_name == "tags":
                new_value = prompts.prompt_tags(repository.get_tags(), default=task.tags)
                if new_value != old_value:
                    task.tags = new_value
                    changes["tags"] = (old_value, new_value)

            elif field_name == "links":
                new_value = prompts.prompt_links(default=task.links)
                if new_value != old_value:
                    task.links = new_value
                    changes["links"] = (old_value, new_value)

            elif field_name == "due":
                new_value = prompts.prompt_due_date(default=task.due)
                if new_value != old_value:
                    task.due = new_value
                    changes["due"] = (old_value, new_value)

            elif field_name == "parent":
                new_value = prompts.prompt_parent(default=task.parent)
                if new_value != old_value:
                    task.parent = new_value
                    changes["parent"] = (old_value, new_value)

            elif field_name == "depends":
                new_value = prompts.prompt_depends(default=task.depends)
                if new_value != old_value:
                    task.depends = new_value
                    changes["depends"] = (old_value, new_value)

            elif field_name == "description":
                new_value = prompts.prompt_description(default=task.description)
                if new_value != old_value:
                    task.description = new_value
                    changes["description"] = (old_value, new_value)

    # If changes were made, update timestamp and save
    if changes:
        task.modified = datetime.now()
        repository.save_task(task)
        show_change_summary(changes)
        return True
    else:
        click.echo("\nNo changes made.")
        return False


@click.command()
@click.argument("task_ids", nargs=-1, required=True)
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
# Single-value field options
@click.option("--title", help="Update task title")
@click.option(
    "--status",
    type=click.Choice(["pending", "in-progress", "completed", "cancelled"], case_sensitive=False),
    help="Update task status",
)
@click.option("--priority", type=click.Choice(["H", "M", "L"], case_sensitive=False), help="Update task priority")
@click.option("--project", "-p", help="Update project name")
@click.option("--due", help="Update due date (e.g., 'tomorrow', '2025-12-31')")
@click.option("--description", "-d", help="Update task description")
@click.option("--parent", "-P", help="Update parent task ID")
# List fields - Replace mode
@click.option("--assignees", "-a", help="Replace all assignees (comma-separated, e.g., '@alice,@bob')")
@click.option("--tags", "-t", help="Replace all tags (comma-separated)")
@click.option("--links", "-l", help="Replace all links (comma-separated URLs)")
@click.option("--depends", help="Replace all dependencies (comma-separated task IDs)")
# List fields - Add mode
@click.option("--add-assignees", help="Add assignees (comma-separated)")
@click.option("--add-tags", help="Add tags (comma-separated)")
@click.option("--add-links", help="Add links (comma-separated URLs)")
@click.option("--add-depends", help="Add dependencies (comma-separated task IDs)")
# List fields - Remove mode
@click.option("--remove-assignees", help="Remove assignees (comma-separated)")
@click.option("--remove-tags", help="Remove tags (comma-separated)")
@click.option("--remove-links", help="Remove links (comma-separated URLs)")
@click.option("--remove-depends", help="Remove dependencies (comma-separated task IDs)")
# Control options
@click.option("--editor", is_flag=True, help="Use text editor instead of interactive prompts")
@click.option("--edit-mode", is_flag=True, help="Open editor after applying changes (single task only)")
@click.option("--editor-command", default=None, help="Editor to use (overrides $EDITOR and config)")
@click.pass_context
def edit(
    ctx,
    task_ids: Tuple[str, ...],
    repo,
    title,
    status,
    priority,
    project,
    due,
    description,
    parent,
    assignees,
    tags,
    links,
    depends,
    add_assignees,
    add_tags,
    add_links,
    add_depends,
    remove_assignees,
    remove_tags,
    remove_links,
    remove_depends,
    editor,
    edit_mode,
    editor_command,
):
    r"""Edit one or more tasks.

    Supports multiple tasks at once using space-separated or comma-separated IDs.

    TASK_IDS: One or more task IDs or titles to edit

    \b
    Single task examples:
      tsk edit 1                                   # Open editor
      tsk edit 1 --priority L                      # Quick priority change
      tsk edit 1 --status in-progress --add-tags urgent
      tsk edit 1 --assignees @alice,@bob           # Replace assignees
      tsk edit 1 --priority H --edit-mode          # Change then review in editor

    \b
    Batch editing examples (space-separated):
      tsk edit 12 13 14 --project mAIcrobe         # Set project for multiple tasks
      tsk edit -p mAIcrobe 12 13 14 15 16          # Same using short option
      tsk edit 10 11 12 --priority H --add-tags urgent
      tsk edit 5 6 7 --assignees @alice            # Set same assignee for all

    \b
    Batch editing examples (comma-separated):
      tsk edit 12,13,14 --project mAIcrobe         # Comma-separated also works
      tsk edit 5,6,7 --assignees @alice            # Set same assignee for all
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Flatten comma-separated task IDs (supports both "12 13 14" and "12,13,14")
    task_id_list = []
    for task_id in task_ids:
        task_id_list.extend([tid.strip() for tid in task_id.split(",")])

    # Check if any field options were provided
    has_field_changes = any(
        [
            title,
            status,
            priority,
            project,
            due,
            description,
            parent,
            assignees,
            tags,
            links,
            depends,
            add_assignees,
            add_tags,
            add_links,
            add_depends,
            remove_assignees,
            remove_tags,
            remove_links,
            remove_depends,
        ]
    )

    # Validation for batch vs single task modes
    is_batch = len(task_id_list) > 1

    if is_batch and not has_field_changes:
        click.secho("Error: Batch editing requires at least one field option", fg="red", err=True)
        click.echo("Use field options like --project, --status, --priority, etc.")
        ctx.exit(1)

    if is_batch and edit_mode:
        click.secho("Error: --edit-mode flag cannot be used with batch editing", fg="red", err=True)
        ctx.exit(1)

    # Handle single task with no field changes
    if len(task_id_list) == 1 and not has_field_changes:
        task_id = task_id_list[0]
        result = find_task_by_title_or_id(manager, task_id, repo)
        task, repository = select_task_from_result(ctx, result, task_id)

        if editor:
            # Use editor mode
            editor_cmd = editor_command or os.environ.get("EDITOR") or config.default_editor or "vim"

            # Create temporary file with task content
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                temp_file = Path(f.name)
                f.write(task.to_markdown())

            # Open editor
            try:
                subprocess.run([editor_cmd, str(temp_file)], check=True)
            except subprocess.CalledProcessError:
                click.secho(f"Error: Editor '{editor_cmd}' failed", fg="red", err=True)
                temp_file.unlink()
                ctx.exit(1)
            except FileNotFoundError:
                click.secho(f"Error: Editor '{editor_cmd}' not found", fg="red", err=True)
                temp_file.unlink()
                ctx.exit(1)

            # Read modified content
            try:
                content = temp_file.read_text()
                modified_task = Task.from_markdown(content, task.id, repository.name)
            except Exception as e:
                click.secho(f"Error: Failed to parse edited task: {e}", fg="red", err=True)
                temp_file.unlink()
                ctx.exit(1)
            finally:
                temp_file.unlink()

            # Save modified task
            repository.save_task(modified_task)
            click.secho(f"✓ Task updated: {modified_task}", fg="green")
        else:
            # Use interactive prompts (default)
            _edit_task_interactive(task, repository)

        click.echo()

        # Update cache and display repository tasks
        update_cache_and_display_repo(manager, repository, config)
        return

    # Batch processing or single task with field changes
    updated_tasks = []
    failed_tasks = []
    repositories_to_update = set()

    for task_id in task_id_list:
        try:
            # Try to find task by ID or title
            result = find_task_by_title_or_id(manager, task_id, repo)

            # Handle the result manually for batch processing
            if result[0] is None:
                # Not found
                if is_batch:
                    click.secho(f"✗ No task found matching '{task_id}'", fg="red")
                    failed_tasks.append(task_id)
                    continue
                else:
                    click.secho(f"Error: No task found matching '{task_id}'", fg="red", err=True)
                    ctx.exit(1)

            elif isinstance(result[0], list):
                # Multiple matches
                if is_batch:
                    click.secho(f"✗ Multiple tasks found matching '{task_id}' - skipping", fg="red")
                    failed_tasks.append(task_id)
                    continue
                else:
                    # Let select_task_from_result handle the interactive selection
                    task, repository = select_task_from_result(ctx, result, task_id)
            else:
                # Single match found
                task, repository = result

            # Apply field changes
            changes = {}

            # Single-value fields
            if title is not None:
                old_title = task.title
                task.title = title
                changes["title"] = (old_title, task.title)

            if status is not None:
                old_status = task.status
                task.status = status.lower()
                changes["status"] = (old_status, task.status)

            if priority is not None:
                old_priority = task.priority
                task.priority = priority.upper()
                changes["priority"] = (old_priority, task.priority)

            if project is not None:
                old_project = task.project
                task.project = project if project else None
                changes["project"] = (old_project, task.project)

            if description is not None:
                old_description = task.description
                task.description = description
                changes["description"] = (old_description, task.description)

            if parent is not None:
                old_parent = task.parent
                task.parent = parent if parent else None
                changes["parent"] = (old_parent, task.parent)

            if due is not None:
                old_due = task.due
                try:
                    parsed_due = dateparser.parse(due, settings={"PREFER_DATES_FROM": "future"})
                    if parsed_due is None:
                        error_msg = (
                            f"Could not parse due date '{due}'\n"
                            f"Supported formats: tomorrow, 2025-12-31, 'Oct 30', 'next week'"
                        )
                        if is_batch:
                            click.secho(f"✗ {error_msg} - skipping task '{task_id}'", fg="red")
                            failed_tasks.append(task_id)
                            continue
                        else:
                            click.secho(f"Error: {error_msg}", fg="red", err=True)
                            ctx.exit(1)
                    task.due = parsed_due
                    changes["due"] = (old_due, task.due)
                except Exception as e:
                    error_msg = (
                        f"Invalid due date '{due}': {e}\nSupported formats: tomorrow, 2025-12-31, 'Oct 30', 'next week'"
                    )
                    if is_batch:
                        click.secho(f"✗ {error_msg} - skipping task '{task_id}'", fg="red")
                        failed_tasks.append(task_id)
                        continue
                    else:
                        click.secho(f"Error: {error_msg}", fg="red", err=True)
                        ctx.exit(1)

            # List fields - Replace mode
            if assignees is not None:
                old_assignees = task.assignees.copy()
                assignee_list = parse_list_field(assignees)
                # Ensure @ prefix
                assignee_list = [a if a.startswith("@") else f"@{a}" for a in assignee_list]
                task.assignees = assignee_list
                changes["assignees"] = (old_assignees, task.assignees)

            if tags is not None:
                old_tags = task.tags.copy()
                task.tags = parse_list_field(tags)
                changes["tags"] = (old_tags, task.tags)

            if links is not None:
                old_links = task.links.copy()
                link_list = parse_list_field(links)
                # Validate URLs
                for link in link_list:
                    if not Task.validate_url(link):
                        if is_batch:
                            click.secho(f"✗ Invalid URL '{link}' for task '{task_id}' - skipping", fg="red")
                            failed_tasks.append(task_id)
                            continue
                        else:
                            click.secho(f"Error: Invalid URL: {link}", fg="red", err=True)
                            ctx.exit(1)
                task.links = link_list
                changes["links"] = (old_links, task.links)

            if depends is not None:
                old_depends = task.depends.copy()
                task.depends = parse_list_field(depends)
                changes["depends"] = (old_depends, task.depends)

            # List fields - Add mode
            if add_assignees:
                old_assignees = task.assignees.copy()
                additions = parse_list_field(add_assignees)
                additions = [a if a.startswith("@") else f"@{a}" for a in additions]
                task.assignees = add_to_list_field(task.assignees, additions)
                if old_assignees != task.assignees:
                    changes["assignees"] = (old_assignees, task.assignees)

            if add_tags:
                old_tags = task.tags.copy()
                task.tags = add_to_list_field(task.tags, parse_list_field(add_tags))
                if old_tags != task.tags:
                    changes["tags"] = (old_tags, task.tags)

            if add_links:
                old_links = task.links.copy()
                additions = parse_list_field(add_links)
                for link in additions:
                    if not Task.validate_url(link):
                        if is_batch:
                            click.secho(f"✗ Invalid URL '{link}' for task '{task_id}' - skipping", fg="red")
                            failed_tasks.append(task_id)
                            continue
                        else:
                            click.secho(f"Error: Invalid URL: {link}", fg="red", err=True)
                            ctx.exit(1)
                task.links = add_to_list_field(task.links, additions)
                if old_links != task.links:
                    changes["links"] = (old_links, task.links)

            if add_depends:
                old_depends = task.depends.copy()
                task.depends = add_to_list_field(task.depends, parse_list_field(add_depends))
                if old_depends != task.depends:
                    changes["depends"] = (old_depends, task.depends)

            # List fields - Remove mode
            if remove_assignees:
                old_assignees = task.assignees.copy()
                removals = parse_list_field(remove_assignees)
                removals = [a if a.startswith("@") else f"@{a}" for a in removals]
                task.assignees = remove_from_list_field(task.assignees, removals)
                if old_assignees != task.assignees:
                    changes["assignees"] = (old_assignees, task.assignees)

            if remove_tags:
                old_tags = task.tags.copy()
                task.tags = remove_from_list_field(task.tags, parse_list_field(remove_tags))
                if old_tags != task.tags:
                    changes["tags"] = (old_tags, task.tags)

            if remove_links:
                old_links = task.links.copy()
                task.links = remove_from_list_field(task.links, parse_list_field(remove_links))
                if old_links != task.links:
                    changes["links"] = (old_links, task.links)

            if remove_depends:
                old_depends = task.depends.copy()
                task.depends = remove_from_list_field(task.depends, parse_list_field(remove_depends))
                if old_depends != task.depends:
                    changes["depends"] = (old_depends, task.depends)

            # Check for subtasks if status was changed (only for single task operations)
            if "status" in changes and not is_batch:
                old_status, new_status = changes["status"]

                # Archiving: changing TO completed
                if new_status == "completed" and old_status != "completed":
                    prompt_for_subtask_archiving(manager, task, batch_mode=False)

                # Unarchiving: changing FROM completed to something else
                elif old_status == "completed" and new_status != "completed":
                    prompt_for_subtask_unarchiving(manager, task, new_status, batch_mode=False)

            # Update modified timestamp
            task.modified = datetime.now()

            # If --edit-mode flag is set, open editor with changes (single task only)
            if edit_mode and not is_batch:
                # Determine editor
                editor_cmd = editor_command or os.environ.get("EDITOR") or config.default_editor or "vim"

                # Create temporary file with task content
                with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                    temp_file = Path(f.name)
                    f.write(task.to_markdown())

                # Open editor
                try:
                    subprocess.run([editor_cmd, str(temp_file)], check=True)
                except subprocess.CalledProcessError:
                    click.secho(f"Error: Editor '{editor_cmd}' failed", fg="red", err=True)
                    temp_file.unlink()
                    ctx.exit(1)
                except FileNotFoundError:
                    click.secho(f"Error: Editor '{editor_cmd}' not found", fg="red", err=True)
                    temp_file.unlink()
                    ctx.exit(1)

                # Read modified content
                try:
                    content = temp_file.read_text()
                    task = Task.from_markdown(content, task.id, repository.name)
                except Exception as e:
                    click.secho(f"Error: Failed to parse edited task: {e}", fg="red", err=True)
                    temp_file.unlink()
                    ctx.exit(1)
                finally:
                    temp_file.unlink()

            # Save modified task
            repository.save_task(task)

            # Track successful update
            updated_tasks.append((task, repository, changes))
            repositories_to_update.add(repository)

            # Show individual update (only if batch mode or single with changes)
            if is_batch or changes:
                click.secho(f"✓ Updated task: {task}", fg="green")

        except Exception as e:
            # Unexpected error - show message and continue with next task
            failed_tasks.append(task_id)
            if is_batch:
                click.secho(f"✗ Could not update task '{task_id}': {e}", fg="red")
            else:
                click.secho(f"Error: Could not update task '{task_id}': {e}", fg="red", err=True)
                ctx.exit(1)

    # Show summary for successful updates
    if updated_tasks:
        # Show changes summary for single task operations
        if not is_batch and len(updated_tasks) == 1:
            _, _, changes = updated_tasks[0]
            show_change_summary(changes)
            click.echo()

        # Show batch summary
        if is_batch:
            click.echo()
            click.secho(f"Updated {len(updated_tasks)} of {len(task_id_list)} tasks", fg="green")

    # Update cache and display for affected repositories
    if repositories_to_update:
        first_repo = list(repositories_to_update)[0]
        click.echo()
        update_cache_and_display_repo(manager, first_repo, config)
