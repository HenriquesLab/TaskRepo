"""Edit command for modifying existing tasks."""

import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import click
import dateparser

from taskrepo.core.repository import RepositoryManager
from taskrepo.core.task import Task
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result, update_cache_and_display_repo


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


@click.command()
@click.argument("task_id")
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
# Single-value field options
@click.option("--title", help="Update task title")
@click.option(
    "--status",
    type=click.Choice(["pending", "in_progress", "completed", "cancelled"], case_sensitive=False),
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
@click.option("--edit", is_flag=True, help="Open editor after applying changes")
@click.option("--editor-command", default=None, help="Editor to use (overrides $EDITOR and config)")
@click.pass_context
def edit(
    ctx,
    task_id,
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
    edit,
    editor_command,
):
    r"""Edit an existing task.

    TASK_ID: Task ID or title to edit

    \b
    Examples:
      tsk edit 1 --priority L                      # Quick priority change
      tsk edit 1 --status in_progress --add-tags urgent
      tsk edit 1 --assignees @alice,@bob           # Replace assignees
      tsk edit 1 --add-assignees @charlie          # Add assignee
      tsk edit 1 --priority H --edit               # Change then review in editor
      tsk edit 1                                   # Open editor (default)
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Try to find task by ID or title
    result = find_task_by_title_or_id(manager, task_id, repo)
    task, repository = select_task_from_result(ctx, result, task_id)

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

    if has_field_changes:
        # Apply direct field changes
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
                    click.secho(f"Error: Could not parse due date: {due}", fg="red", err=True)
                    ctx.exit(1)
                task.due = parsed_due
                changes["due"] = (old_due, task.due)
            except Exception as e:
                click.secho(f"Error: Invalid due date: {e}", fg="red", err=True)
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

        # Update modified timestamp
        task.modified = datetime.now()

        # If --edit flag is set, open editor with changes
        if edit:
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

        # Show changes summary
        show_change_summary(changes)
        click.echo()
        click.secho(f"✓ Task updated: {task}", fg="green")
        click.echo()

    else:
        # No field options - open editor (original behavior)
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
        click.echo()

    # Update cache and display repository tasks
    update_cache_and_display_repo(manager, repository, config)
