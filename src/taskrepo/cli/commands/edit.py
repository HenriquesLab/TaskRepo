"""Edit command for modifying existing tasks."""

import subprocess
import tempfile
from pathlib import Path

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.core.task import Task


@click.command()
@click.argument("task_id")
@click.option("--repo", "-r", help="Repository name (will search all repos if not specified)")
@click.option("--editor", "-e", envvar="EDITOR", default="vim", help="Editor to use (defaults to $EDITOR or vim)")
@click.pass_context
def edit(ctx, task_id, repo, editor):
    """Edit an existing task.

    TASK_ID: Task ID to edit
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Find the task
    if repo:
        repository = manager.get_repository(repo)
        if not repository:
            click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
            ctx.exit(1)
        task = repository.get_task(task_id)
        if not task:
            click.secho(f"Error: Task '{task_id}' not found in repository '{repo}'", fg="red", err=True)
            ctx.exit(1)
    else:
        # Search all repositories
        task = None
        repository = None
        for r in manager.discover_repositories():
            t = r.get_task(task_id)
            if t:
                task = t
                repository = r
                break

        if not task:
            click.secho(f"Error: Task '{task_id}' not found", fg="red", err=True)
            ctx.exit(1)

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
