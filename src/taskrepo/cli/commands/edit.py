"""Edit command for modifying existing tasks."""

import os
import subprocess
import tempfile
from pathlib import Path

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.core.task import Task
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.helpers import find_task_by_title_or_id
from taskrepo.utils.id_mapping import save_id_cache


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

    # Update cache with ALL active tasks across all repos
    all_tasks_all_repos = manager.list_all_tasks()
    active_tasks_all = [t for t in all_tasks_all_repos if t.status != "completed"]
    save_id_cache(active_tasks_all)

    # Display tasks from this repository only (filtered view)
    repo_tasks = repository.list_tasks()
    active_tasks_repo = [t for t in repo_tasks if t.status != "completed"]

    if active_tasks_repo:
        display_tasks_table(active_tasks_repo, config, save_cache=False)
