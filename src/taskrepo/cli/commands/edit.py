"""Edit command for modifying existing tasks."""

import os
import subprocess
import tempfile
from pathlib import Path

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.core.task import Task
from taskrepo.utils.helpers import find_task_by_title_or_id, select_task_from_result, update_cache_and_display_repo


@click.command()
@click.argument("task_id")
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.option("--editor", "-e", default=None, help="Editor to use (overrides $EDITOR and config)")
@click.pass_context
def edit(ctx, task_id, repo, editor):
    """Edit an existing task.

    TASK_ID: Task ID or title to edit
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Determine editor with priority: CLI option > $EDITOR > config.default_editor > 'vim'
    if not editor:
        editor = os.environ.get("EDITOR") or config.default_editor or "vim"

    # Try to find task by ID or title
    result = find_task_by_title_or_id(manager, task_id, repo)
    task, repository = select_task_from_result(ctx, result, task_id)

    # Create temporary file with task content
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        temp_file = Path(f.name)
        f.write(task.to_markdown())

    # Open editor
    try:
        subprocess.run([editor, str(temp_file)], check=True)
    except subprocess.CalledProcessError:
        click.secho(f"Error: Editor '{editor}' failed", fg="red", err=True)
        temp_file.unlink()
        ctx.exit(1)
    except FileNotFoundError:
        click.secho(f"Error: Editor '{editor}' not found", fg="red", err=True)
        temp_file.unlink()
        ctx.exit(1)

    # Read modified content
    try:
        content = temp_file.read_text()
        modified_task = Task.from_markdown(content, task_id, repository.name)
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
