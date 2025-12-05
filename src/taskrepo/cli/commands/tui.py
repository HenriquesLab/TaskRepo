"""TUI command for interactive task management."""

import subprocess
import tempfile
import threading
from pathlib import Path

import click
from rich.console import Console

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui import prompts
from taskrepo.tui.task_tui import TaskTUI
from taskrepo.utils.conflict_detection import display_conflict_warning, scan_all_repositories
from taskrepo.utils.id_mapping import save_id_cache
from taskrepo.utils.sorting import sort_tasks

# Global flag to track background sync status
_background_sync_completed = False
_background_sync_running = False
_background_sync_completion_time = None
_background_sync_error = False


def _mark_as_not_synced(task_tui: TaskTUI):
    """Mark TUI as having unsaved changes after local modifications and clear task cache."""
    from taskrepo.core.repository import clear_task_cache

    task_tui.sync_status = "idle"
    task_tui.has_unsaved_changes = True  # Track that there are local changes
    task_tui.sync_message = None
    # Note: We preserve last_sync_time so the status bar can show "Synced X ago (unsaved)"

    # Clear task cache so modified tasks are re-loaded with fresh data
    clear_task_cache()


def _background_sync(config):
    """Run sync in background thread using subprocess to avoid terminal interference."""
    import time

    from taskrepo.utils.sync_history import SyncHistory

    global \
        _background_sync_completed, \
        _background_sync_running, \
        _background_sync_completion_time, \
        _background_sync_error

    _background_sync_running = True
    _background_sync_completed = False
    _background_sync_completion_time = None
    _background_sync_error = False

    # Load sync history for recording
    sync_history = SyncHistory()

    try:
        # Find the taskrepo executable (might be 'tsk' or 'taskrepo')
        import shutil

        tsk_cmd = shutil.which("tsk") or shutil.which("taskrepo")
        if not tsk_cmd:
            # Fallback: try to use python module invocation
            tsk_cmd = None

        # Run sync as subprocess with output suppressed to avoid interfering with TUI
        if tsk_cmd:
            result = subprocess.run(
                [tsk_cmd, "sync"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=300,  # 5 minute timeout
            )
        else:
            # Fallback: invoke as python module
            import sys

            result = subprocess.run(
                [sys.executable, "-m", "taskrepo.cli.main", "sync"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=300,  # 5 minute timeout
            )

        if result.returncode == 0:
            _background_sync_completed = True
            _background_sync_completion_time = time.time()
            # Record successful sync to history (repo details not available from subprocess)
            sync_history.add_entry(success=True, repos_synced=["all"], repos_failed=[])
        else:
            # Sync command failed (non-zero exit code)
            _background_sync_error = True
            # Record failed sync to history
            sync_history.add_entry(
                success=False,
                repos_synced=[],
                repos_failed=["unknown"],
                error_message="Sync subprocess returned non-zero exit code",
            )
    except subprocess.TimeoutExpired:
        # Timeout error
        _background_sync_error = True
        sync_history.add_entry(
            success=False, repos_synced=[], repos_failed=["unknown"], error_message="Sync timed out after 5 minutes"
        )
    except Exception as e:
        # Other error
        _background_sync_error = True
        sync_history.add_entry(success=False, repos_synced=[], repos_failed=["unknown"], error_message=str(e))
    finally:
        _background_sync_running = False


@click.command()
@click.option("--repo", "-r", help="Start in specific repository")
@click.option("--no-sync", is_flag=True, help="Disable automatic background sync on startup")
@click.pass_context
def tui(ctx, repo, no_sync):
    """Launch interactive TUI for task management.

    By default, a background sync runs automatically on startup.
    Use --no-sync to disable this behavior.

    The TUI provides a full-screen interface for managing tasks with keyboard shortcuts:

    Navigation:
        ↑/↓ - Navigate tasks
        ←/→ - Switch between items (repos/projects/assignees)
        Tab - Switch view type (repo/project/assignee)
        Space - Multi-select tasks

    Task Operations:
        a - Add new task
        e - Edit task
        d - Mark as done
        p - Toggle in-progress/pending
        c - Mark as cancelled
        H - Set priority to High
        M - Set priority to Medium
        L - Set priority to Low
        v - Archive task
        l - Delete task
        m - Move task to another repo
        u - Create subtask
        t - Extend due date

    View Controls:
        / - Filter tasks
        s - Sync with git
        r - Toggle tree view
        q/Esc - Quit
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)
    repositories = manager.discover_repositories()

    if not repositories:
        click.secho("No repositories found.", fg="red", err=True)
        click.echo("Create one with: tsk create-repo")
        ctx.exit(1)

    # Clear sync error log at start of TUI session
    sync_error_log = Path.home() / ".TaskRepo" / "sync_error.log"
    if sync_error_log.exists():
        sync_error_log.unlink()

    # Initialize sync history (loads existing history from disk)
    from taskrepo.utils.sync_history import SyncHistory

    SyncHistory()  # Load existing history from disk to initialize the singleton

    # Check for merge conflicts and auto-resolve if possible
    parent_path = Path(config.parent_dir).expanduser()

    # First scan to count total conflicts
    all_conflicts = scan_all_repositories(parent_path, auto_resolve=False)
    total_conflicts = sum(len(files) for files in all_conflicts.values())

    # Scan again with auto-resolve enabled
    unresolved_conflicts = scan_all_repositories(parent_path, auto_resolve=True)
    auto_resolved_count = total_conflicts - sum(len(files) for files in unresolved_conflicts.values())

    # Show warning if there are conflicts (resolved or unresolved)
    if total_conflicts > 0:
        console = Console()
        display_conflict_warning(unresolved_conflicts, console, auto_resolved=auto_resolved_count)

        # Only prompt if there are still unresolved conflicts
        if unresolved_conflicts:
            if not click.confirm("Continue anyway?", default=False):
                click.echo("Aborted. Please resolve conflicts first with: tsk sync")
                ctx.exit(1)

    # Start background sync unless disabled
    if not no_sync:
        sync_thread = threading.Thread(target=_background_sync, args=(config,), daemon=True)
        sync_thread.start()

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
    sorted_tasks = sort_tasks(all_tasks, config, all_tasks=all_tasks)
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
        elif result == "subtask":
            _handle_subtask(task_tui, config)
        elif result == "extend":
            _handle_extend(task_tui, config)
        elif result == "priority-high":
            _handle_priority_change(task_tui, "H")
        elif result == "priority-medium":
            _handle_priority_change(task_tui, "M")
        elif result == "priority-low":
            _handle_priority_change(task_tui, "L")
        elif result == "info":
            _handle_info_task(task_tui)
        elif result == "sync":
            _handle_sync(task_tui, config)

        # Save selected_row and viewport_top AFTER handler runs to capture any adjustments (e.g., from _force_reload)
        saved_selected_row = task_tui.selected_row
        saved_viewport_top = task_tui.viewport_top

        # Update ID cache after task operations
        all_tasks = manager.list_all_tasks(include_archived=False)
        sorted_tasks = sort_tasks(all_tasks, config, all_tasks=all_tasks)
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
        # Restore selected row and viewport position (ensure they're within bounds)
        tasks = task_tui._get_filtered_tasks()
        if tasks:
            task_tui.selected_row = min(saved_selected_row, len(tasks) - 1)
            task_tui.viewport_top = min(saved_viewport_top, max(0, len(tasks) - 1))
        else:
            task_tui.selected_row = 0
            task_tui.viewport_top = 0


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
    _mark_as_not_synced(task_tui)
    task_tui._force_reload()
    click.secho(f"\n✓ Created task: {task.title}", fg="green")


def _handle_edit_task(task_tui: TaskTUI, config):
    """Handle editing selected task(s)."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        return

    if len(selected_tasks) > 1:
        click.secho("\n⚠ Cannot edit multiple tasks. Select only one.", fg="yellow")
        return

    task = selected_tasks[0]

    # Find the repository for this task
    repo = task_tui._get_current_repo()
    if not repo:
        # When on "All" tab, find the repo by task's repo name
        repo = next((r for r in task_tui.repositories if r.name == task.repo), None)
        if not repo:
            click.secho(f"\n✗ Could not find repository for task: {task.repo}", fg="red")
            return

    # Ask user to choose edit mode
    click.echo("\n" + "=" * 50)
    click.echo(f"Edit Task: {task.title}")
    click.echo("=" * 50)
    click.echo("\nEdit mode:")
    click.echo("  (i) Interactive prompts (default)")
    click.echo("  (e) Text editor")

    try:
        mode = click.prompt("\nChoose mode", type=str, default="i").lower()
    except (click.Abort, EOFError):
        click.echo("\nCancelled.")
        return

    if mode == "e":
        # Use editor mode
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
                _mark_as_not_synced(task_tui)
                click.secho(f"\n✓ Updated task: {updated_task.title}", fg="green")
                # Force immediate reload to show changes
                task_tui._force_reload()
            else:
                click.echo("\nNo changes made.")

        except Exception as e:
            click.secho(f"\n✗ Error editing task: {e}", fg="red")
        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
    else:
        # Use interactive prompts (default)
        from taskrepo.cli.commands.edit import _edit_task_interactive

        changed = _edit_task_interactive(task, repo)
        if changed:
            _mark_as_not_synced(task_tui)
            # Force immediate reload to show changes
            task_tui._force_reload()


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

    # Mark TUI as not synced since we made local changes
    _mark_as_not_synced(task_tui)

    # Force immediate reload to show changes
    task_tui._force_reload()

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

    # Mark TUI as not synced since we made local changes
    _mark_as_not_synced(task_tui)

    # Force immediate reload to show changes
    # If status change removes task from view (completed/cancelled), select task above
    removes_from_view = new_status in ["completed", "cancelled"]
    task_tui._force_reload(select_above=removes_from_view)

    # Clear multi-selection (no message, immediate return to TUI)
    task_tui.multi_selected.clear()


def _handle_priority_change(task_tui: TaskTUI, new_priority: str):
    """Handle changing priority of selected task(s)."""
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

        task.priority = new_priority
        task.modified = datetime.now()
        repo.save_task(task)

    # Mark TUI as not synced since we made local changes
    _mark_as_not_synced(task_tui)

    # Force immediate reload to show changes
    task_tui._force_reload()

    # Clear multi-selection (no message, immediate return to TUI)
    task_tui.multi_selected.clear()


def _handle_delete_task(task_tui: TaskTUI):
    """Handle deleting selected task(s)."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        return

    # Confirm deletion
    if len(selected_tasks) == 1:
        message = f"Delete task '{selected_tasks[0].title}'?"
    else:
        message = f"Delete {len(selected_tasks)} tasks?"

    click.echo(f"\n{message}")
    if not prompts.confirm_single_key("Confirm deletion?"):
        click.echo("Cancelled.")
        return

    # Delete each task from its respective repository
    for task in selected_tasks:
        # Find the repository for this task by name (works in all view modes)
        repo = next((r for r in task_tui.repositories if r.name == task.repo), None)

        if not repo:
            click.secho(f"\n✗ Could not find repository for task: {task.repo}", fg="red")
            continue

        repo.delete_task(task.id)

    # Mark TUI as not synced since we made local changes
    _mark_as_not_synced(task_tui)
    # Select task above after deleting
    task_tui._force_reload(select_above=True)

    if len(selected_tasks) == 1:
        click.secho(f"\n✓ Deleted task: {selected_tasks[0].title}", fg="green")
    else:
        click.secho(f"\n✓ Deleted {len(selected_tasks)} tasks", fg="green")

    # Clear multi-selection
    task_tui.multi_selected.clear()


def _handle_archive_task(task_tui: TaskTUI, config):
    """Handle archiving selected task(s)."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        return

    # Confirm archiving
    if len(selected_tasks) == 1:
        message = f"Archive task '{selected_tasks[0].title}'?"
    else:
        message = f"Archive {len(selected_tasks)} tasks?"

    click.echo(f"\n{message}")
    if not prompts.confirm_single_key("Confirm archiving?"):
        click.echo("Cancelled.")
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
        # Mark TUI as not synced since we made local changes
        _mark_as_not_synced(task_tui)
        # Select task above after archiving
        task_tui._force_reload(select_above=True)

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
        return

    # Prompt for target repository
    click.echo("\n" + "=" * 50)
    click.echo("Move Task(s) to Repository")
    click.echo("=" * 50)

    target_repo = prompts.prompt_repository(task_tui.repositories)
    if not target_repo:
        click.echo("Cancelled.")
        return

    # Confirm move
    if len(selected_tasks) == 1:
        message = f"Move '{selected_tasks[0].title}' to repository '{target_repo.name}'?"
    else:
        message = f"Move {len(selected_tasks)} tasks to repository '{target_repo.name}'?"

    click.echo(f"\n{message}")
    if not prompts.confirm_single_key("Confirm move?"):
        click.echo("Cancelled.")
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
                if prompts.confirm_single_key("Move subtasks as well?"):
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
        # Mark TUI as not synced since we made local changes
        _mark_as_not_synced(task_tui)
        task_tui._force_reload()

        if len(selected_tasks) == 1:
            click.secho(f"\n✓ Moved task to '{target_repo.name}': {selected_tasks[0].title}", fg="green")
        else:
            click.secho(f"\n✓ Moved {moved_count} of {len(selected_tasks)} tasks to '{target_repo.name}'", fg="green")

    # Clear multi-selection
    task_tui.multi_selected.clear()


def _is_task_archived(repository, task_id: str) -> bool:
    """Check if a task is archived."""
    archive_path = repository.path / "tasks" / "archive" / f"task-{task_id}.md"
    return archive_path.exists()


def _handle_subtask(task_tui: TaskTUI, config):
    """Handle creating a subtask under the selected task."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        return

    if len(selected_tasks) > 1:
        click.secho("\n⚠ Cannot create subtask under multiple tasks. Select only one task.", fg="yellow")
        return

    parent_task = selected_tasks[0]

    # Find the repository for this task
    repo = next((r for r in task_tui.repositories if r.name == parent_task.repo), None)
    if not repo:
        click.secho(f"\n✗ Could not find repository for task: {parent_task.repo}", fg="red")
        return

    # Use existing interactive prompts
    click.echo("\n" + "=" * 50)
    click.echo(f"Create Subtask under: {parent_task.title}")
    click.echo("=" * 50)

    title = prompts.prompt_title()
    if not title:
        click.echo("Cancelled.")
        return

    # Get existing values for autocomplete
    existing_projects = repo.get_projects()
    existing_assignees = repo.get_assignees()
    existing_tags = repo.get_tags()

    # Prompt for other task details
    project = prompts.prompt_project(existing_projects, default=parent_task.project)
    priority = prompts.prompt_priority(default=config.default_priority or "M")
    assignees = prompts.prompt_assignees(existing_assignees, default=parent_task.assignees)
    tags = prompts.prompt_tags(existing_tags, default=parent_task.tags)
    links = prompts.prompt_links()
    due_date = prompts.prompt_due_date()
    description = prompts.prompt_description()

    # Create the task
    from datetime import datetime

    from taskrepo.core.task import Task

    task = Task(
        id=repo.next_task_id(),
        title=title,
        status=config.default_status or "pending",
        project=project,
        priority=priority,
        assignees=assignees,
        tags=tags,
        links=links,
        parent=parent_task.id,  # Set parent to create subtask relationship
        due=due_date,
        description=description,
        created=datetime.now(),
        modified=datetime.now(),
        repo=repo.name,
    )

    repo.save_task(task)
    _mark_as_not_synced(task_tui)
    task_tui._force_reload()
    click.secho(f"\n✓ Created subtask: {task.title}", fg="green")

    # Clear multi-selection
    task_tui.multi_selected.clear()


def _handle_extend(task_tui: TaskTUI, config):
    """Handle extending task due date(s)."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        return

    click.echo("\n" + "=" * 50)
    click.echo(f"Extend Task Due Date{'s' if len(selected_tasks) > 1 else ''}")
    click.echo("=" * 50)

    # Show selected tasks
    if len(selected_tasks) == 1:
        task = selected_tasks[0]
        click.echo(f"\nTask: {task.title}")
        if task.due:
            click.echo(f"Current due date: {task.due.strftime('%Y-%m-%d')}")
        else:
            click.echo("Current due date: None")
    else:
        click.echo(f"\n{len(selected_tasks)} tasks selected")

    # Prompt for date or duration
    click.echo("\nEnter date or duration:")
    click.echo("  Durations: 1w, 2d, 3m, 1y (extends from current due date)")
    click.echo("  Keywords: today, tomorrow, next week, next month, next year")
    click.echo("  Weekdays: next monday, this friday, monday")
    click.echo("  ISO dates: 2025-10-30")
    click.echo("  Natural dates: 'Oct 30', 'October 30 2025'")

    date_input = click.prompt("\nDate or duration", type=str, default="")
    if not date_input:
        click.echo("Cancelled.")
        return

    # Parse date or duration
    from taskrepo.utils.date_parser import parse_date_or_duration

    try:
        parsed_value, is_absolute_date = parse_date_or_duration(date_input)
    except ValueError as e:
        click.secho(f"\n✗ Error: {e}", fg="red")
        return

    # Apply to all selected tasks
    from datetime import datetime

    extended_count = 0
    for task in selected_tasks:
        # Find the repository for this task
        repo = next((r for r in task_tui.repositories if r.name == task.repo), None)
        if not repo:
            continue

        # Calculate new due date
        if is_absolute_date:
            # Set to specific date
            new_due = parsed_value
        else:
            # Extend by duration
            if task.due:
                new_due = task.due + parsed_value
            else:
                new_due = datetime.now() + parsed_value

        # Update task
        task.due = new_due
        task.modified = datetime.now()
        repo.save_task(task)
        extended_count += 1

    # Show result
    if extended_count > 0:
        # Mark TUI as not synced since we made local changes
        _mark_as_not_synced(task_tui)
        task_tui._force_reload()

        action_verb = "Updated" if is_absolute_date else "Extended"
        if len(selected_tasks) == 1:
            click.secho(f"\n✓ {action_verb} task: {selected_tasks[0].title}", fg="green")
        else:
            click.secho(f"\n✓ {action_verb} {extended_count} task{'s' if extended_count != 1 else ''}", fg="green")
    else:
        click.secho("\n✗ Failed to update any tasks", fg="red")

    # Clear multi-selection
    task_tui.multi_selected.clear()


def _handle_info_task(task_tui: TaskTUI):
    """Handle viewing task info."""
    selected_tasks = task_tui._get_selected_tasks()
    if not selected_tasks:
        return

    if len(selected_tasks) > 1:
        click.secho("\n⚠ Select only one task to view details.", fg="yellow")
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


def _handle_sync(task_tui: TaskTUI, config):
    """Handle syncing with git."""
    from git import GitCommandError

    from taskrepo.tui.conflict_resolver import resolve_conflict_interactive
    from taskrepo.utils.merge import detect_conflicts, smart_merge_tasks
    from taskrepo.utils.sync_history import SyncHistory

    # Track sync results for history
    repos_synced = []
    repos_failed = []
    error_messages = []

    # Determine which repositories to sync based on current view
    if task_tui.current_view_idx == -1:
        # Viewing "All" - sync all repositories
        repositories_to_sync = task_tui.repositories
        click.echo("\n" + "=" * 50)
        click.echo("Syncing All Repositories")
        click.echo("=" * 50)
    else:
        # Viewing specific item - find relevant repositories
        if task_tui.view_mode == "repo":
            # Sync specific repository
            repo = task_tui._get_current_repo()
            if not repo:
                click.echo("\nNo repository selected.")
                return
            repositories_to_sync = [repo]
            click.echo("\n" + "=" * 50)
            click.echo(f"Syncing Repository: {repo.name}")
            click.echo("=" * 50)
        elif task_tui.view_mode == "project":
            # Find repositories with tasks in this project
            current_project = task_tui.view_items[task_tui.current_view_idx]
            repo_names = set()
            for repo in task_tui.repositories:
                for task in repo.list_tasks():
                    if task.project == current_project:
                        repo_names.add(repo.name)
                        break
            repositories_to_sync = [r for r in task_tui.repositories if r.name in repo_names]
            click.echo("\n" + "=" * 50)
            click.echo(f"Syncing Repositories with project '{current_project}' ({len(repositories_to_sync)} repos)")
            click.echo("=" * 50)
        elif task_tui.view_mode == "assignee":
            # Find repositories with tasks assigned to this user
            current_assignee = task_tui.view_items[task_tui.current_view_idx]
            repo_names = set()
            for repo in task_tui.repositories:
                for task in repo.list_tasks():
                    if current_assignee in task.assignees:
                        repo_names.add(repo.name)
                        break
            repositories_to_sync = [r for r in task_tui.repositories if r.name in repo_names]
            click.echo("\n" + "=" * 50)
            click.echo(f"Syncing Repositories for assignee '{current_assignee}' ({len(repositories_to_sync)} repos)")
            click.echo("=" * 50)
        else:
            # Fallback: sync all
            repositories_to_sync = task_tui.repositories
            click.echo("\n" + "=" * 50)
            click.echo("Syncing All Repositories")
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
                # Check for unexpected files before committing
                from taskrepo.utils.file_validation import (
                    add_to_gitignore,
                    delete_unexpected_files,
                    detect_unexpected_files,
                    prompt_unexpected_files,
                )

                unexpected = detect_unexpected_files(git_repo, repository.path)

                if unexpected:
                    action = prompt_unexpected_files(unexpected, repository.name)

                    if action == "ignore":
                        # Add patterns to .gitignore
                        patterns = list(unexpected.keys())
                        add_to_gitignore(patterns, repository.path)
                        # Stage .gitignore change
                        git_repo.git.add(".gitignore")
                    elif action == "delete":
                        # Delete the files
                        delete_unexpected_files(unexpected, repository.path)
                    elif action == "skip":
                        # Skip this repository
                        click.secho("  ⊗ Skipped repository", fg="yellow")
                        continue
                    # If "commit", proceed as normal

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
                pull_succeeded = True
                try:
                    click.echo("  • Pulling from remote...")
                    # Use --rebase=false to handle divergent branches
                    git_repo.git.pull("--rebase=false", "origin", git_repo.active_branch.name)
                    click.secho("  ✓ Pulled from remote", fg="green")
                except GitCommandError as e:
                    if "would be overwritten" in str(e) or "conflict" in str(e).lower():
                        pull_succeeded = False
                        click.secho("  ⚠ Pull created conflicts", fg="yellow")
                    else:
                        raise

                # Check for conflict markers after pull
                from rich.console import Console

                from taskrepo.cli.commands.sync import _has_conflict_markers, _resolve_conflict_markers

                if not pull_succeeded or _has_conflict_markers(repository.path):
                    click.echo("  • Resolving conflict markers...")
                    console = Console()
                    resolved_files = _resolve_conflict_markers(repository, console)

                    if resolved_files:
                        click.secho(f"  ✓ Auto-resolved {len(resolved_files)} conflicted file(s)", fg="green")

                        # Commit the resolutions
                        for file_path in resolved_files:
                            git_repo.git.add(str(file_path))
                        git_repo.index.commit(f"Auto-resolve: Fixed {len(resolved_files)} conflict marker(s)")
                        click.secho("  ✓ Committed conflict resolutions", fg="green")

                # Push to remote
                click.echo("  • Pushing to remote...")

                def try_push():
                    repo_origin = git_repo.remotes.origin  # noqa: B023
                    push_info = repo_origin.push()
                    # Check if push failed by examining PushInfo flags
                    for info in push_info:
                        if info.flags & info.ERROR:
                            raise GitCommandError("git push", f"Push failed with ERROR flag: {info.summary}")
                        if info.flags & info.REJECTED:
                            # Non-fast-forward - will attempt auto-recovery
                            raise GitCommandError("git push", "REJECTED")
                        if info.flags & info.REMOTE_REJECTED:
                            raise GitCommandError("git push", f"Remote rejected push: {info.summary}")
                        if info.flags & info.REMOTE_FAILURE:
                            raise GitCommandError("git push", f"Remote failure during push: {info.summary}")
                    return push_info

                try:
                    try_push()
                    click.secho("  ✓ Pushed to remote", fg="green")
                except GitCommandError as e:
                    # Check if this is a non-fast-forward rejection that we can auto-recover
                    if "REJECTED" in str(e):
                        click.secho("  ⚠ Push rejected (branches diverged) - attempting auto-recovery...", fg="yellow")

                        # Try to pull with rebase
                        try:
                            click.echo("  • Pulling with rebase...")
                            current_branch = git_repo.active_branch.name
                            git_repo.git.pull("--rebase", "origin", current_branch)

                            # Check if rebase created conflicts
                            if git_repo.is_dirty(working_tree=True, untracked_files=False):
                                # Rebase created conflicts - abort and report
                                click.secho("  ✗ Rebase created conflicts - aborting auto-recovery", fg="red")
                                try:
                                    git_repo.git.rebase("--abort")
                                    click.secho("  → Aborted rebase", fg="yellow")
                                except Exception:
                                    pass
                                click.secho(
                                    "  → Manual resolution required: git pull --rebase && git push", fg="yellow"
                                )
                                raise
                            else:
                                # Rebase succeeded - try push again
                                click.secho("  ✓ Rebase successful", fg="green")
                                click.echo("  • Pushing to remote (retry)...")

                                try_push()
                                click.secho("  ✓ Pushed to remote", fg="green")

                        except GitCommandError as rebase_error:
                            # Rebase or retry push failed
                            if "conflict" in str(rebase_error).lower():
                                click.secho("  ✗ Auto-recovery failed: conflicts during rebase", fg="red")
                                click.secho("  → Resolve manually: git pull --rebase && git push", fg="yellow")
                            raise
                    else:
                        # Other push error - re-raise
                        raise
            else:
                click.secho("  ℹ No remote configured (local-only repository)", fg="cyan")

            # Record successful sync
            repos_synced.append(repository.name)

        except GitCommandError as e:
            click.secho(f"  ✗ Git error: {e}", fg="red")
            repos_failed.append(repository.name)
            error_messages.append(f"{repository.name}: Git error - {str(e)}")
        except Exception as e:
            click.secho(f"  ✗ Error: {e}", fg="red")
            repos_failed.append(repository.name)
            error_messages.append(f"{repository.name}: {str(e)}")

    click.echo("\n" + "=" * 50)
    click.secho("Sync complete!", fg="green")
    click.echo("=" * 50)

    # Record sync to history
    import time

    sync_history = SyncHistory()
    overall_success = len(repos_failed) == 0
    error_summary = "; ".join(error_messages) if error_messages else None

    sync_history.add_entry(
        success=overall_success,
        repos_synced=repos_synced,
        repos_failed=repos_failed,
        error_message=error_summary,
    )

    # Mark as synced and clear unsaved changes flag
    task_tui.last_sync_time = time.time()
    task_tui.has_unsaved_changes = False
    task_tui.sync_status = "success" if overall_success else "error"
