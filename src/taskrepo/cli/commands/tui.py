"""TUI command for interactive task management."""

import subprocess
import tempfile
from pathlib import Path

import click
from prompt_toolkit.shortcuts import confirm

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui import prompts
from taskrepo.tui.task_tui import TaskTUI
from taskrepo.utils.id_mapping import save_id_cache
from taskrepo.utils.sorting import sort_tasks


@click.command()
@click.option("--repo", "-r", help="Start in specific repository")
@click.pass_context
def tui(ctx, repo):
    """Launch interactive TUI for task management.

    The TUI provides a full-screen interface for managing tasks with keyboard shortcuts:

    Navigation:
        ↑/↓ - Navigate tasks
        ←/→ - Switch between items (repos/projects/assignees)
        Tab - Switch view type (repo/project/assignee)
        Space - Multi-select tasks

    Task Operations:
        n - New task
        e - Edit task
        d - Mark as done
        p - Toggle in-progress/pending
        c - Mark as cancelled
        a - Archive task
        x - Delete task

    View Controls:
        / - Filter tasks
        s - Sync with git
        t - Toggle tree view
        r - Refresh
        q/Esc - Quit
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)
    repositories = manager.discover_repositories()

    if not repositories:
        click.secho("No repositories found.", fg="red", err=True)
        click.echo("Create one with: tsk create-repo")
        ctx.exit(1)

    # If repo specified, find its index and start there
    start_repo_idx = -1  # Default to "All" tab
    if repo:
        try:
            start_repo_idx = next(i for i, r in enumerate(repositories) if r.name == repo)
        except StopIteration:
            click.secho(f"Repository '{repo}' not found.", fg="red", err=True)
            ctx.exit(1)

    # Update ID cache with all tasks before starting TUI
    manager = RepositoryManager(config.parent_dir)
    all_tasks = manager.list_all_tasks(include_archived=False)
    sorted_tasks = sort_tasks(all_tasks, config)
    save_id_cache(sorted_tasks)

    # Create and run TUI in a loop
    task_tui = TaskTUI(config, repositories)
    # Set the starting view index
    task_tui.current_view_idx = start_repo_idx

    while True:
        result = task_tui.run()

        if result is None:
            # User quit (q or Esc)
            break

        # Save current view state before handling action
        saved_view_mode = task_tui.view_mode
        saved_view_idx = task_tui.current_view_idx
        saved_filter_text = task_tui.filter_text
        saved_tree_view = task_tui.tree_view

        # Handle the action
        if result == "new":
            _handle_new_task(task_tui, config)
        elif result == "edit":
            _handle_edit_task(task_tui, config)
        elif result == "done":
            _handle_status_change(task_tui, "completed")
        elif result == "in-progress":
            _handle_in_progress_toggle(task_tui)
        elif result == "cancelled":
            _handle_status_change(task_tui, "cancelled")
        elif result == "delete":
            _handle_delete_task(task_tui)
        elif result == "archive":
            _handle_archive_task(task_tui, config)
        elif result == "move":
            _handle_move_task(task_tui, config)
        elif result == "info":
            _handle_info_task(task_tui)
        elif result == "sync":
            _handle_sync(task_tui, config)

        # Update ID cache after task operations
        all_tasks = manager.list_all_tasks(include_archived=False)
        sorted_tasks = sort_tasks(all_tasks, config)
        save_id_cache(sorted_tasks)

        # Recreate TUI to refresh, restoring view state
        task_tui = TaskTUI(config, repositories)
        task_tui.view_mode = saved_view_mode
        task_tui.current_view_idx = saved_view_idx
        task_tui.filter_text = saved_filter_text
        task_tui.filter_input.text = saved_filter_text  # Also restore the filter input widget
        task_tui.tree_view = saved_tree_view
        # Update config to match restored view mode
        config.tui_view_mode = saved_view_mode
        # Rebuild view items with restored state
        task_tui.view_items = task_tui._build_view_items()


def _handle_new_task(task_tui: TaskTUI, config):
    """Handle creating a new task."""
    repo = task_tui._get_current_repo()

    # If on "All" tab, prompt user to select a repository
    if not repo:
        click.echo("\n" + "=" * 50)
        click.echo("Create New Task")
        click.echo("=" * 50)
        repo = prompts.prompt_repository(task_tui.repositories)
        if not repo:
            click.echo("Cancelled.")
            click.echo("Press Enter to continue...")
            input()
            return

    # Use existing interactive prompts
    click.echo("\n" + "=" * 50)
    click.echo("Create New Task")
    click.echo("=" * 50)

    title = prompts.prompt_title()
    if not title:
        click.echo("Cancelled.")
        return

    project = prompts.prompt_project(repo.get_projects())
    assignees = prompts.prompt_assignees(repo.get_assignees())
    priority = prompts.prompt_priority(config.default_priority)
    tags = prompts.prompt_tags(repo.get_tags())
    links = prompts.prompt_links()
    due = prompts.prompt_due_date()
    description = prompts.prompt_description()

    # Create task
    from datetime import datetime

    from taskrepo.core.task import Task

    task = Task(
        id=repo.next_task_id(),
        title=title,
        status=config.default_status,
        priority=priority,
        project=project,
        assignees=assignees,
        tags=tags,
        links=links,
        due=due,
        description=description,
        created=datetime.now(),
        modified=datetime.now(),
        repo=repo.name,
    )

    repo.save_task(task)
    click.secho(f"\n✓ Created task: {task.title}", fg="green")
    click.echo("\nPress Enter to continue...")
    input()


def _handle_edit_task(task_tui: TaskTUI, config):
    """Handle editing selected task(s)."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        click.echo("\nNo task selected.")
        click.echo("Press Enter to continue...")
        input()
        return

    if len(selected_tasks) > 1:
        click.secho("\n⚠ Cannot edit multiple tasks at once. Select only one task.", fg="yellow")
        click.echo("Press Enter to continue...")
        input()
        return

    task = selected_tasks[0]

    # Find the repository for this task
    repo = task_tui._get_current_repo()
    if not repo:
        # When on "All" tab, find the repo by task's repo name
        repo = next((r for r in task_tui.repositories if r.name == task.repo), None)
        if not repo:
            click.secho(f"\n✗ Could not find repository for task: {task.repo}", fg="red")
            click.echo("Press Enter to continue...")
            input()
            return

    # Open task in editor
    editor = config.default_editor or "nano"

    # Create temp file with task content
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(task.to_markdown())
        temp_path = f.name

    try:
        # Open editor
        subprocess.run([editor, temp_path], check=True)

        # Read back the modified content
        with open(temp_path) as f:
            content = f.read()

        # Parse and save
        from taskrepo.core.task import Task

        updated_task = Task.from_markdown(content, task_id=task.id, repo=repo.name)
        updated_task.modified = task.modified  # Preserve original modified time initially

        # Update modified time if content changed
        if updated_task.to_markdown() != task.to_markdown():
            from datetime import datetime

            updated_task.modified = datetime.now()
            repo.save_task(updated_task)
            click.secho(f"\n✓ Updated task: {updated_task.title}", fg="green")
        else:
            click.echo("\nNo changes made.")

    except Exception as e:
        click.secho(f"\n✗ Error editing task: {e}", fg="red")
    finally:
        # Clean up temp file
        Path(temp_path).unlink(missing_ok=True)

    click.echo("Press Enter to continue...")
    input()


def _handle_in_progress_toggle(task_tui: TaskTUI):
    """Handle toggling between in-progress and pending status."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        # Silently return if no task selected
        return

    from datetime import datetime

    # Update each task in its respective repository
    for task in selected_tasks:
        # Find the repository for this task by name (works in all view modes)
        repo = next((r for r in task_tui.repositories if r.name == task.repo), None)

        if not repo:
            # Skip this task if repo not found
            continue

        # Toggle: if in-progress, set to pending; otherwise, set to in-progress
        if task.status == "in-progress":
            task.status = "pending"
        else:
            task.status = "in-progress"

        task.modified = datetime.now()
        repo.save_task(task)

    # Clear multi-selection (no message, immediate return to TUI)
    task_tui.multi_selected.clear()


def _handle_status_change(task_tui: TaskTUI, new_status: str):
    """Handle changing status of selected task(s)."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        # Silently return if no task selected
        return

    from datetime import datetime

    # Update each task in its respective repository
    for task in selected_tasks:
        # Find the repository for this task by name (works in all view modes)
        repo = next((r for r in task_tui.repositories if r.name == task.repo), None)

        if not repo:
            # Skip this task if repo not found
            continue

        task.status = new_status
        task.modified = datetime.now()
        repo.save_task(task)

    # Clear multi-selection (no message, immediate return to TUI)
    task_tui.multi_selected.clear()


def _handle_delete_task(task_tui: TaskTUI):
    """Handle deleting selected task(s)."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        click.echo("\nNo task selected.")
        click.echo("Press Enter to continue...")
        input()
        return

    # Confirm deletion
    if len(selected_tasks) == 1:
        message = f"Delete task '{selected_tasks[0].title}'?"
    else:
        message = f"Delete {len(selected_tasks)} tasks?"

    click.echo(f"\n{message}")
    if not confirm("Confirm deletion?"):
        click.echo("Cancelled.")
        click.echo("Press Enter to continue...")
        input()
        return

    # Delete each task from its respective repository
    for task in selected_tasks:
        # Find the repository for this task by name (works in all view modes)
        repo = next((r for r in task_tui.repositories if r.name == task.repo), None)

        if not repo:
            click.secho(f"\n✗ Could not find repository for task: {task.repo}", fg="red")
            continue

        repo.delete_task(task.id)

    if len(selected_tasks) == 1:
        click.secho(f"\n✓ Deleted task: {selected_tasks[0].title}", fg="green")
    else:
        click.secho(f"\n✓ Deleted {len(selected_tasks)} tasks", fg="green")

    click.echo("Press Enter to continue...")
    input()

    # Clear multi-selection
    task_tui.multi_selected.clear()


def _handle_archive_task(task_tui: TaskTUI, config):
    """Handle archiving selected task(s)."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        click.echo("\nNo task selected.")
        click.echo("Press Enter to continue...")
        input()
        return

    # Confirm archiving
    if len(selected_tasks) == 1:
        message = f"Archive task '{selected_tasks[0].title}'?"
    else:
        message = f"Archive {len(selected_tasks)} tasks?"

    click.echo(f"\n{message}")
    if not confirm("Confirm archiving?"):
        click.echo("Cancelled.")
        click.echo("Press Enter to continue...")
        input()
        return

    # Archive each task from its respective repository
    archived_count = 0
    for task in selected_tasks:
        # Find the repository for this task by name (works in all view modes)
        repo = next((r for r in task_tui.repositories if r.name == task.repo), None)

        if not repo:
            click.secho(f"\n✗ Could not find repository for task: {task.repo}", fg="red")
            continue

        if repo.archive_task(task.id):
            archived_count += 1
        else:
            click.secho(f"\n✗ Could not archive task: {task.title}", fg="red")

    if archived_count > 0:
        if len(selected_tasks) == 1:
            click.secho(f"\n✓ Archived task: {selected_tasks[0].title}", fg="green")
        else:
            click.secho(f"\n✓ Archived {archived_count} of {len(selected_tasks)} tasks", fg="green")

    # Clear multi-selection
    task_tui.multi_selected.clear()


def _handle_move_task(task_tui: TaskTUI, config):
    """Handle moving selected task(s) to another repository."""
    from datetime import datetime

    from taskrepo.core.repository import RepositoryManager
    from taskrepo.tui import prompts

    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        click.echo("\nNo task selected.")
        click.echo("Press Enter to continue...")
        input()
        return

    # Prompt for target repository
    click.echo("\n" + "=" * 50)
    click.echo("Move Task(s) to Repository")
    click.echo("=" * 50)

    target_repo = prompts.prompt_repository(task_tui.repositories)
    if not target_repo:
        click.echo("Cancelled.")
        click.echo("Press Enter to continue...")
        input()
        return

    # Confirm move
    if len(selected_tasks) == 1:
        message = f"Move '{selected_tasks[0].title}' to repository '{target_repo.name}'?"
    else:
        message = f"Move {len(selected_tasks)} tasks to repository '{target_repo.name}'?"

    click.echo(f"\n{message}")
    if not confirm("Confirm move?"):
        click.echo("Cancelled.")
        click.echo("Press Enter to continue...")
        input()
        return

    # Initialize manager for subtask checking
    manager = RepositoryManager(config.parent_dir)

    # Move each task
    moved_count = 0
    for task in selected_tasks:
        # Find source repository
        source_repo = next((r for r in task_tui.repositories if r.name == task.repo), None)
        if not source_repo:
            click.secho(f"\n✗ Could not find repository for task: {task.repo}", fg="red")
            continue

        # Don't move if already in target repo
        if source_repo.name == target_repo.name:
            click.secho(f"\n⚠ Task '{task.title}' is already in '{target_repo.name}'", fg="yellow")
            continue

        try:
            # Check for subtasks
            subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)
            move_subtasks = False

            if subtasks_with_repos:
                click.echo(f"\nTask '{task.title}' has {len(subtasks_with_repos)} subtask(s).")
                if confirm("Move subtasks as well?"):
                    move_subtasks = True

            # Check for dependencies
            if task.depends:
                click.secho(
                    f"\n⚠ Warning: Task '{task.title}' has {len(task.depends)} "
                    f"dependenc{'y' if len(task.depends) == 1 else 'ies'}.",
                    fg="yellow",
                )

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

            moved_count += 1

        except Exception as e:
            click.secho(f"\n✗ Failed to move task '{task.title}': {str(e)}", fg="red")

    if moved_count > 0:
        if len(selected_tasks) == 1:
            click.secho(f"\n✓ Moved task to '{target_repo.name}': {selected_tasks[0].title}", fg="green")
        else:
            click.secho(f"\n✓ Moved {moved_count} of {len(selected_tasks)} tasks to '{target_repo.name}'", fg="green")

    click.echo("Press Enter to continue...")
    input()

    # Clear multi-selection
    task_tui.multi_selected.clear()


def _is_task_archived(repository, task_id: str) -> bool:
    """Check if a task is archived."""
    archive_path = repository.path / "tasks" / "archive" / f"task-{task_id}.md"
    return archive_path.exists()


def _handle_info_task(task_tui: TaskTUI):
    """Handle viewing task info."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        click.echo("\nNo task selected.")
        click.echo("Press Enter to continue...")
        input()
        return

    if len(selected_tasks) > 1:
        click.secho("\n⚠ Select only one task to view details.", fg="yellow")
        click.echo("Press Enter to continue...")
        input()
        return

    task = selected_tasks[0]

    # Display task info
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    click.echo("\n")

    # Create info table
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan bold")
    table.add_column("Value", style="white")

    table.add_row("ID", task.id)
    table.add_row("Title", task.title)
    table.add_row("Status", task.status)
    table.add_row("Priority", task.priority)
    table.add_row("Project", task.project or "-")
    table.add_row("Assignees", ", ".join(task.assignees) if task.assignees else "-")
    table.add_row("Tags", ", ".join(task.tags) if task.tags else "-")
    table.add_row("Links", "\n".join(task.links) if task.links else "-")
    table.add_row("Due", task.due.strftime("%Y-%m-%d %H:%M:%S") if task.due else "-")
    table.add_row("Created", task.created.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("Modified", task.modified.strftime("%Y-%m-%d %H:%M:%S"))

    if task.description:
        table.add_row("Description", task.description)

    console.print(Panel(table, title=f"Task: {task.title}", border_style="blue"))

    click.echo("\nPress Enter to continue...")
    input()


def _handle_sort_change(task_tui: TaskTUI, config):
    """Handle changing sort order."""
    sort_options = [
        ("priority", "Priority"),
        ("due", "Due Date"),
        ("created", "Created Date"),
        ("modified", "Modified Date"),
        ("status", "Status"),
        ("title", "Title"),
        ("project", "Project"),
    ]

    click.echo("\n" + "=" * 50)
    click.echo("Change Sort Order")
    click.echo("=" * 50)
    click.echo("\nCurrent sort order:", ", ".join(config.sort_by))
    click.echo("\nAvailable sort fields:")
    for idx, (code, name) in enumerate(sort_options, 1):
        click.echo(f"  {idx}. {name} ({code})")

    click.echo("\nEnter comma-separated fields (e.g., 'due,priority' or '1,2')")
    click.echo("Prefix with '-' for descending order (e.g., '-priority' or '-1')")

    try:
        choice = input("\nSort by: ").strip()
        if not choice:
            click.echo("Cancelled.")
            click.echo("Press Enter to continue...")
            input()
            return

        # Parse choice
        new_sort_fields = []
        for field in choice.split(","):
            field = field.strip()
            if not field:
                continue

            # Check if it's a number (index) or field name
            descending = field.startswith("-")
            if descending:
                field = field[1:]

            # Try to parse as number
            try:
                idx = int(field)
                if 1 <= idx <= len(sort_options):
                    field_code = sort_options[idx - 1][0]
                else:
                    click.secho(f"Invalid option: {idx}", fg="yellow")
                    continue
            except ValueError:
                # Use as field name
                field_code = field

            # Add to list
            if descending:
                new_sort_fields.append(f"-{field_code}")
            else:
                new_sort_fields.append(field_code)

        if new_sort_fields:
            config.sort_by = new_sort_fields
            # Note: This only changes the in-memory config
            # To persist, we'd need to save to config file
            click.secho(f"\n✓ Sort order changed to: {', '.join(new_sort_fields)}", fg="green")
        else:
            click.echo("No valid fields provided.")

    except (KeyboardInterrupt, EOFError):
        click.echo("\nCancelled.")

    click.echo("Press Enter to continue...")
    input()


def _handle_sync(task_tui: TaskTUI, config):
    """Handle syncing with git."""
    from git import GitCommandError

    from taskrepo.tui.conflict_resolver import resolve_conflict_interactive
    from taskrepo.utils.merge import detect_conflicts, smart_merge_tasks

    # Determine which repositories to sync
    if task_tui.current_view_idx == -1:
        # Sync all repositories
        repositories_to_sync = task_tui.repositories
        click.echo("\n" + "=" * 50)
        click.echo("Syncing All Repositories")
        click.echo("=" * 50)
    else:
        # Sync current repository
        repo = task_tui._get_current_repo()
        if not repo:
            click.echo("\nNo repository selected.")
            click.echo("Press Enter to continue...")
            input()
            return
        repositories_to_sync = [repo]
        click.echo("\n" + "=" * 50)
        click.echo(f"Syncing Repository: {repo.name}")
        click.echo("=" * 50)

    for repository in repositories_to_sync:
        git_repo = repository.git_repo

        # Display repository
        if git_repo.remotes:
            remote_url = git_repo.remotes.origin.url
            click.echo(f"\n{repository.name} ({remote_url})")
        else:
            click.echo(f"\n{repository.name} (local: {repository.path})")

        try:
            # Commit local changes
            if git_repo.is_dirty(untracked_files=True):
                click.echo("  • Committing local changes...")
                git_repo.git.add(A=True)
                git_repo.index.commit("Auto-commit: TaskRepo sync")
                click.secho("  ✓ Changes committed", fg="green")

            # Check if remote exists
            if git_repo.remotes:
                # Detect conflicts before pulling
                click.echo("  • Checking for conflicts...")
                conflicts = detect_conflicts(git_repo, repository.path)

                if conflicts:
                    click.secho(f"  ⚠ Found {len(conflicts)} conflicting task(s)", fg="yellow")
                    resolved_count = 0

                    for conflict in conflicts:
                        # Use auto-merge strategy
                        if conflict.can_auto_merge:
                            resolved_task = smart_merge_tasks(
                                conflict.local_task, conflict.remote_task, conflict.conflicting_fields
                            )
                            if resolved_task:
                                click.echo(f"    • {conflict.file_path.name}: Auto-merged")
                                repository.save_task(resolved_task)
                                resolved_count += 1
                            else:
                                # Fall back to interactive
                                resolved_task = resolve_conflict_interactive(conflict, config.default_editor)
                                if resolved_task:
                                    repository.save_task(resolved_task)
                                    resolved_count += 1
                        else:
                            # Requires manual resolution
                            resolved_task = resolve_conflict_interactive(conflict, config.default_editor)
                            if resolved_task:
                                repository.save_task(resolved_task)
                                resolved_count += 1

                    if resolved_count > 0:
                        click.secho(f"  ✓ Resolved {resolved_count} conflict(s)", fg="green")

                # Pull from remote
                click.echo("  • Pulling from remote...")
                origin = git_repo.remotes.origin
                # Use --rebase=false to handle divergent branches
                git_repo.git.pull("--rebase=false", "origin", git_repo.active_branch.name)
                click.secho("  ✓ Pulled from remote", fg="green")

                # Push to remote
                click.echo("  • Pushing to remote...")
                origin.push()
                click.secho("  ✓ Pushed to remote", fg="green")
            else:
                click.secho("  ℹ No remote configured (local-only repository)", fg="cyan")

        except GitCommandError as e:
            click.secho(f"  ✗ Git error: {e}", fg="red")
        except Exception as e:
            click.secho(f"  ✗ Error: {e}", fg="red")

    click.echo("\n" + "=" * 50)
    click.secho("Sync complete!", fg="green")
    click.echo("=" * 50)
    click.echo("\nPress Enter to continue...")
    input()
