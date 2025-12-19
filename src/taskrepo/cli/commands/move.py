"""Move command - Move tasks between repositories."""

import sys
from datetime import datetime
from typing import List, Optional, Tuple

import click
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.validation import Validator

from taskrepo.core.repository import Repository, RepositoryManager
from taskrepo.core.task import Task
from taskrepo.utils.helpers import (
    find_task_by_title_or_id,
    select_task_from_result,
    update_cache_and_display_repo,
)


@click.command()
@click.argument("task_ids", nargs=-1, required=True)
@click.option(
    "--repo",
    "-r",
    help="Source repository to search (search all repos if not specified)",
)
@click.option(
    "--to",
    "-t",
    required=True,
    help="Target repository name to move task(s) to",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation and automatically move subtasks",
)
@click.pass_context
def move(ctx, task_ids: Tuple[str, ...], repo: Optional[str], to: str, force: bool):
    """Move one or more tasks to a different repository.

    Supports multiple tasks at once using space-separated or comma-separated IDs.

    Examples:
        # Move a single task to 'personal' repository

        tsk move 5 --to personal

        # Move multiple tasks to 'work' repository (space-separated)

        tsk move 12 13 14 --to work

        # Move multiple tasks to 'work' repository (comma-separated)

        tsk move 12,13,14 --to work

        # Move from specific source repo to target repo

        tsk move "Fix bug" --repo work --to archive-2024

        # Skip confirmation prompt

        tsk move 8 --to personal --force
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Validate that target repository exists
    target_repo = manager.get_repository(to)
    if not target_repo:
        click.secho(f"Error: Target repository '{to}' not found.", fg="red", err=True)
        click.echo("\nAvailable repositories:")
        for r in manager.discover_repositories():
            click.echo(f"  - {r.name}")
        ctx.exit(1)

    moved_tasks: List[Tuple[Task, Repository, Repository]] = []
    failed_tasks: List[str] = []
    repositories_to_update = set()

    # Flatten comma-separated task IDs (supports both "12 13 14" and "12,13,14")
    task_id_list = []
    for task_id in task_ids:
        task_id_list.extend([tid.strip() for tid in task_id.split(",")])

    for task_id in task_id_list:
        try:
            # Find task by ID, UUID, or title
            result = find_task_by_title_or_id(manager, task_id, repo)

            # Handle not found / multiple matches
            if result[0] is None:
                if len(task_id_list) > 1:
                    click.secho(f"✗ No task found matching '{task_id}'", fg="red")
                    failed_tasks.append(task_id)
                    continue
                else:
                    click.secho(
                        f"Error: No task found matching '{task_id}'",
                        fg="red",
                        err=True,
                    )
                    ctx.exit(1)

            task, source_repo = select_task_from_result(ctx, result, task_id)

            # Check if task is already in target repo
            if source_repo.name == target_repo.name:
                if len(task_id_list) > 1:
                    click.secho(
                        f"⚠ Task '{task.title}' is already in repository '{to}'",
                        fg="yellow",
                    )
                    failed_tasks.append(task_id)
                    continue
                else:
                    click.secho(
                        f"Error: Task is already in repository '{to}'",
                        fg="yellow",
                        err=True,
                    )
                    ctx.exit(1)

            moved_tasks.append((task, source_repo, target_repo))
            repositories_to_update.add(source_repo)
            repositories_to_update.add(target_repo)

        except Exception as e:
            if len(task_id_list) > 1:
                click.secho(f"✗ Error processing task '{task_id}': {str(e)}", fg="red")
                failed_tasks.append(task_id)
                continue
            else:
                click.secho(
                    f"Error processing task '{task_id}': {str(e)}",
                    fg="red",
                    err=True,
                )
                ctx.exit(1)

    if not moved_tasks:
        click.secho("No tasks to move.", fg="yellow")
        ctx.exit(0)

    # Confirm move operation
    if not force:
        # Check if we're in a terminal - if not, skip confirmation
        if not sys.stdin.isatty():
            pass  # Automatically confirm when not in terminal
        else:
            click.echo()
            if len(moved_tasks) == 1:
                task, source_repo, _ = moved_tasks[0]
                click.echo(f"Move task '{task.title}' from '{source_repo.name}' to '{to}'?")
            else:
                click.echo(f"Move {len(moved_tasks)} task(s) to repository '{to}'?")

            yn_validator = Validator.from_callable(
                lambda text: text.lower() in ["y", "n", "yes", "no"],
                error_message="Please enter 'y' or 'n'",
                move_cursor_to_end=True,
            )

            response = prompt(
                "Confirm move? (Y/n) ",
                default="y",
                validator=yn_validator,
            ).lower()

            if response not in ["y", "yes"]:
                click.echo("Cancelled.")
                ctx.exit(0)

    click.echo()

    # Process each task
    successfully_moved = []
    for task, source_repo, target_repo in moved_tasks:
        try:
            # Check for subtasks
            subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)
            move_subtasks = force  # Default to --force flag value

            if subtasks_with_repos and not force:
                # Check if we're in a terminal - if not, default to yes
                if not sys.stdin.isatty():
                    move_subtasks = True
                else:
                    click.echo(f"\nTask '{task.title}' has {len(subtasks_with_repos)} subtask(s).")

                    yn_validator = Validator.from_callable(
                        lambda text: text.lower() in ["y", "n", "yes", "no"],
                        error_message="Please enter 'y' or 'n'",
                        move_cursor_to_end=True,
                    )

                    response = prompt(
                        "Move subtasks as well? (Y/n) ",
                        default="y",
                        validator=yn_validator,
                    ).lower()

                    move_subtasks = response in ["y", "yes"]

            # Check for dependencies
            if task.depends:
                click.secho(
                    f"\n⚠ Warning: Task '{task.title}' has {len(task.depends)} "
                    f"dependenc{'y' if len(task.depends) == 1 else 'ies'}.",
                    fg="yellow",
                )
                click.echo("Dependencies may be in different repositories after move.")

            # Check if task depends on other tasks
            dependent_tasks = _find_tasks_depending_on(manager, task.id)
            if dependent_tasks:
                click.secho(
                    f"\n⚠ Warning: {len(dependent_tasks)} other task(s) depend on '{task.title}'.",
                    fg="yellow",
                )
                click.echo("Those tasks may be in different repositories after move.")

            # Check if task is archived
            is_archived = _is_task_archived(source_repo, task.id)

            # Update modified timestamp
            task.modified = datetime.now()

            # Save to target repo (always goes to tasks/ first)
            target_repo.save_task(task)

            # If task was archived, move it to archive/ in target repo
            if is_archived:
                target_repo.archive_task(task.id)

            # Delete from source repo
            source_repo.delete_task(task.id)

            # Move subtasks if requested
            if move_subtasks and subtasks_with_repos:
                for subtask, subtask_repo in subtasks_with_repos:
                    subtask_is_archived = _is_task_archived(subtask_repo, subtask.id)
                    subtask.modified = datetime.now()
                    target_repo.save_task(subtask)
                    if subtask_is_archived:
                        target_repo.archive_task(subtask.id)
                    subtask_repo.delete_task(subtask.id)
                    if subtask_repo != source_repo:
                        repositories_to_update.add(subtask_repo)
            elif subtasks_with_repos and not move_subtasks:
                # Warn user that subtasks are staying behind
                subtask_count = len(subtasks_with_repos)
                subtask_word = "subtask" if subtask_count == 1 else "subtasks"
                click.secho(
                    f"⚠ Warning: {subtask_count} {subtask_word} will remain in original repository.", fg="yellow"
                )

            # Format success message
            assignees_str = f" {', '.join(task.assignees)}" if task.assignees else ""
            project_str = f" [{task.project}]" if task.project else ""
            archived_str = " [archived]" if is_archived else ""
            success_msg = (
                f"{click.style('✓ Moved:', fg='green')} "
                f"{click.style('[' + task.id[:8] + '...]', fg='cyan')} "
                f"{click.style(task.title, fg='yellow', bold=True)}"
                f"{project_str}{assignees_str} ({task.status}, {task.priority}){archived_str}"
            )
            if move_subtasks and subtasks_with_repos:
                success_msg += f" + {len(subtasks_with_repos)} subtask(s)"
            click.echo(success_msg)

            successfully_moved.append(task)

        except Exception as e:
            click.secho(f"✗ Failed to move task '{task.title}': {str(e)}", fg="red")
            failed_tasks.append(task.title)

    # Summary
    click.echo()
    if successfully_moved:
        if len(successfully_moved) == 1:
            click.secho(f"✓ Successfully moved 1 task to '{to}'", fg="green", bold=True)
        else:
            click.secho(
                f"✓ Successfully moved {len(successfully_moved)} tasks to '{to}'",
                fg="green",
                bold=True,
            )

    if failed_tasks:
        click.secho(
            f"✗ Failed to move {len(failed_tasks)} task(s)",
            fg="red",
            bold=True,
        )

    # Update cache and display target repository
    update_cache_and_display_repo(manager, target_repo, config)


def _is_task_archived(repository: Repository, task_id: str) -> bool:
    """Check if a task is archived."""
    archive_path = repository.path / "tasks" / "archive" / f"task-{task_id}.md"
    return archive_path.exists()


def _find_tasks_depending_on(manager: RepositoryManager, task_id: str) -> List[Task]:
    """Find all tasks that depend on the given task."""
    dependent_tasks = []
    all_tasks = manager.list_all_tasks(include_archived=False)

    for task in all_tasks:
        if task.depends and task_id in task.depends:
            dependent_tasks.append(task)

    return dependent_tasks
