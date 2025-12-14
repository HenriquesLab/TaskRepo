"""Sync command for git operations."""

import re
import time
import traceback
from datetime import datetime
from pathlib import Path

import click
from git import GitCommandError
from rich.console import Console
from rich.markup import escape
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn

from taskrepo.core.repository import Repository, RepositoryManager
from taskrepo.core.task import Task
from taskrepo.tui.conflict_resolver import resolve_conflict_interactive
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.conflict_detection import resolve_readme_conflicts
from taskrepo.utils.merge import detect_conflicts, smart_merge_tasks

console = Console()


def _log_sync_error(repo_name: str, error: Exception):
    """Log sync error to ~/.TaskRepo/sync_error.log.

    Args:
        repo_name: Name of repository that encountered error
        error: Exception that occurred
    """
    log_path = Path.home() / ".TaskRepo" / "sync_error.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a") as f:
        f.write(f"\n{'=' * 80}\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"Repository: {repo_name}\n")
        f.write(f"Error Type: {type(error).__name__}\n")
        f.write(f"Error Message: {str(error)}\n")
        f.write("\nTraceback:\n")
        f.write(traceback.format_exc())
        f.write(f"{'=' * 80}\n")


# Pre-compile regex patterns for conflict markers (optimization)
CONFLICT_MARKER_PATTERN = re.compile(r"<<<<<<< HEAD\s*\n(.*?)\n=======\s*\n(.*?)\n>>>>>>> [^\n]*", re.DOTALL)
CONFLICT_MARKER_ALT_PATTERN = re.compile(r"<<<<<<< HEAD(.*?)=======(.*?)>>>>>>> ", re.DOTALL)
CONFLICT_MARKER_EXTRACT_PATTERN = re.compile(r"<<<<<<< HEAD\s*\n(.*?)\n=======\s*\n.*?\n>>>>>>> [^\n]*\n?", re.DOTALL)


class TaskCache:
    """Cache for parsed Task objects to avoid redundant parsing during sync.

    This cache stores Task objects keyed by their file path, allowing
    multiple sync operations to reuse already-parsed tasks instead of
    re-parsing the same files multiple times.
    """

    def __init__(self):
        """Initialize empty cache."""
        self._cache: dict[Path, Task] = {}
        self._file_hashes: dict[Path, int] = {}  # Track content hashes to detect changes

    def get(self, file_path: Path, content: str | None = None) -> Task | None:
        """Get cached task if available and content hasn't changed.

        Args:
            file_path: Path to task file
            content: Optional file content to verify cache validity

        Returns:
            Cached Task object or None if not cached or content changed
        """
        if file_path not in self._cache:
            return None

        # If content provided, verify it hasn't changed
        if content is not None:
            content_hash = hash(content)
            if self._file_hashes.get(file_path) != content_hash:
                # Content changed, invalidate cache entry
                self._cache.pop(file_path, None)
                self._file_hashes.pop(file_path, None)
                return None

        return self._cache.get(file_path)

    def set(self, file_path: Path, task: Task, content: str) -> None:
        """Cache a parsed task.

        Args:
            file_path: Path to task file
            task: Parsed Task object
            content: File content used for parsing (for hash verification)
        """
        self._cache[file_path] = task
        self._file_hashes[file_path] = hash(content)

    def invalidate(self, file_path: Path) -> None:
        """Invalidate cache entry for a specific file.

        Args:
            file_path: Path to task file
        """
        self._cache.pop(file_path, None)
        self._file_hashes.pop(file_path, None)

    def clear(self) -> None:
        """Clear all cached tasks."""
        self._cache.clear()
        self._file_hashes.clear()


class SyncChangeTracker:
    """Track changes during sync to enable smart operations.

    Tracks what changed during sync (commits, conflicts, README updates)
    to avoid redundant operations and provide better user feedback.
    """

    def __init__(self):
        """Initialize change tracker."""
        self.had_uncommitted = False
        self.resolved_conflicts = 0
        self.resolved_markers = 0
        self.pulled_changes = False
        self.readme_changed = False
        self.changes_to_commit: list[str] = []  # List of change descriptions

    def record_uncommitted(self) -> None:
        """Record that there were uncommitted changes."""
        self.had_uncommitted = True
        self.changes_to_commit.append("uncommitted changes")

    def record_conflict_resolution(self, count: int) -> None:
        """Record conflict resolution.

        Args:
            count: Number of conflicts resolved
        """
        self.resolved_conflicts = count
        if count > 0:
            self.changes_to_commit.append(f"{count} conflict(s) resolved")

    def record_marker_resolution(self, count: int) -> None:
        """Record conflict marker resolution.

        Args:
            count: Number of files with markers resolved
        """
        self.resolved_markers = count
        if count > 0:
            self.changes_to_commit.append(f"{count} conflict marker(s) fixed")

    def record_pull(self) -> None:
        """Record that pull brought changes."""
        self.pulled_changes = True

    def record_readme_change(self) -> None:
        """Record that README was updated."""
        self.readme_changed = True
        self.changes_to_commit.append("README updated")

    def should_regenerate_readme(self) -> bool:
        """Determine if README should be regenerated.

        Returns:
            True if README regeneration is needed, False otherwise
        """
        # Regenerate if:
        # - Tasks were modified (conflicts resolved or markers fixed)
        # - Pull brought changes (may include task changes)
        return self.resolved_conflicts > 0 or self.resolved_markers > 0 or self.pulled_changes

    def get_commit_message(self) -> str:
        """Generate consolidated commit message based on changes.

        Returns:
            Commit message describing all changes
        """
        if not self.changes_to_commit:
            return "Auto-sync: TaskRepo sync"

        # Create descriptive message
        return f"Auto-sync: {', '.join(self.changes_to_commit)}"


def run_with_spinner(
    progress: Progress,
    spinner_task: TaskID,
    operation_name: str,
    operation_func,
    verbose: bool = False,
    operations_task: TaskID | None = None,
):
    """Run an operation with a spinner and timing.

    Args:
        progress: Rich Progress instance
        spinner_task: Spinner task ID
        operation_name: Name of operation to display
        operation_func: Function to execute
        verbose: Show timing information
        operations_task: Optional operations progress task to advance
    """
    start_time = time.perf_counter()
    progress.update(spinner_task, description=f"[cyan]{operation_name}...")

    try:
        result = operation_func()
        elapsed = time.perf_counter() - start_time

        if verbose:
            progress.console.print(f"  [green]✓[/green] {operation_name} [dim]({elapsed:.1f}s)[/dim]")
        else:
            progress.console.print(f"  [green]✓[/green] {operation_name}")

        # Advance operations progress if provided
        if operations_task is not None:
            progress.update(operations_task, advance=1)

        return result, elapsed
    except Exception:
        elapsed = time.perf_counter() - start_time
        if verbose:
            progress.console.print(f"  [red]✗[/red] {operation_name} [dim]({elapsed:.1f}s)[/dim]")
        else:
            progress.console.print(f"  [red]✗[/red] {operation_name}")

        # Still advance operations progress on failure
        if operations_task is not None:
            progress.update(operations_task, advance=1)

        raise


@click.command()
@click.option("--repo", "-r", help="Repository name (will sync all repos if not specified)")
@click.option("--push/--no-push", default=True, help="Push changes to remote")
@click.option(
    "--auto-merge/--no-auto-merge",
    default=True,
    help="Automatically merge conflicts when possible (default: True)",
)
@click.option(
    "--strategy",
    type=click.Choice(["auto", "local", "remote", "interactive"], case_sensitive=False),
    default="auto",
    help="Conflict resolution strategy: auto (smart merge), local (keep local), remote (keep remote), interactive (prompt)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed progress and timing information",
)
@click.pass_context
def sync(ctx, repo, push, auto_merge, strategy, verbose):
    """Sync task repositories with git (pull and optionally push)."""
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Get repositories to sync
    if repo:
        repository = manager.get_repository(repo)
        if not repository:
            click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
            ctx.exit(1)
        repositories = [repository]
    else:
        repositories = manager.discover_repositories()

    if not repositories:
        click.echo("No repositories to sync.")
        return

    # Proactive check: Detect repositories with unfinished merges BEFORE starting sync
    repos_with_unfinished_merges = []
    for repository in repositories:
        merge_head_file = repository.path / ".git" / "MERGE_HEAD"
        if merge_head_file.exists():
            repos_with_unfinished_merges.append(repository.name)

    if repos_with_unfinished_merges:
        console.print()
        console.print("[yellow]⚠ Warning: Found repositories with unfinished merges:[/yellow]")
        for repo_name in repos_with_unfinished_merges:
            console.print(f"  • {repo_name}")
        console.print()
        console.print("[cyan]These will be automatically resolved during sync.[/cyan]")
        console.print()

    # Track timing for each repository
    repo_timings = {}
    total_start_time = time.perf_counter()

    # Create progress context with progress bar (for repos or operations)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        # Add overall progress task
        # - For multiple repos: track repository progress
        # - For single repo: track operation progress
        if len(repositories) > 1:
            overall_task = progress.add_task("[bold]Syncing repositories", total=len(repositories), completed=0)
            operations_task = None  # Operations tracking not needed for multi-repo
        else:
            # Estimate operations for single repo (will be adjusted dynamically)
            estimated_ops = 6  # Base: check conflicts, pull, update readme, archive readme, maybe commit/push
            overall_task = progress.add_task("[bold]Syncing operations", total=estimated_ops, completed=0)
            operations_task = overall_task  # Use same task for operations

        # Add spinner task for per-operation status
        spinner_task = progress.add_task("", total=None)

        for repo_index, repository in enumerate(repositories, 1):
            repo_start_time = time.perf_counter()
            git_repo = repository.git_repo

            # Create cache and change tracker for this repository
            task_cache = TaskCache()
            change_tracker = SyncChangeTracker()

            # Display repository with URL or local path
            progress.console.print()
            if git_repo.remotes:
                remote_url = git_repo.remotes.origin.url
                progress.console.print(
                    f"[bold cyan][{repo_index}/{len(repositories)}][/bold cyan] {repository.name} [dim]({remote_url})[/dim]"
                )
            else:
                progress.console.print(
                    f"[bold cyan][{repo_index}/{len(repositories)}][/bold cyan] {repository.name} [dim](local: {repository.path})[/dim]"
                )

            try:
                # Check if there are uncommitted changes (including untracked files)
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
                        progress.console.print("  [yellow]⚠[/yellow] Found unexpected files")
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
                            progress.console.print("  [yellow]⊗[/yellow] Skipped repository")
                            continue
                        # If "commit", proceed as normal

                    # Stage all changes but don't commit yet (will consolidate commits later)
                    def stage_changes():
                        git_repo.git.add(A=True)

                    run_with_spinner(
                        progress, spinner_task, "Staging local changes", stage_changes, verbose, operations_task
                    )
                    change_tracker.record_uncommitted()

                # Check if remote exists
                if git_repo.remotes:
                    # IMPORTANT: Check for unfinished merge FIRST, before any git operations
                    # This prevents "You have not concluded your merge (MERGE_HEAD exists)" errors
                    merge_head_file = repository.path / ".git" / "MERGE_HEAD"
                    if merge_head_file.exists():
                        progress.console.print("  [yellow]⚠[/yellow] Found unfinished merge, attempting to complete...")

                        # Check for conflict markers in task files
                        if _has_conflict_markers(repository.path):
                            progress.console.print("  [yellow]→[/yellow] Resolving conflict markers...")

                            def resolve_markers():
                                return _resolve_conflict_markers(repository, progress.console, task_cache)

                            resolved_files, _ = run_with_spinner(
                                progress, spinner_task, "Resolving conflict markers", resolve_markers, verbose
                            )

                            if resolved_files:
                                # Stage resolved files
                                for resolved_file in resolved_files:
                                    git_repo.index.add([str(resolved_file)])
                                progress.console.print(f"  [green]✓[/green] Resolved {len(resolved_files)} file(s)")

                        # Try to complete the merge
                        try:
                            # Check if all conflicts are resolved (no unstaged changes with conflicts)
                            if not git_repo.is_dirty(working_tree=True, untracked_files=False):
                                # Working tree is clean, safe to commit
                                git_repo.git.commit("-m", "Auto-sync: Completed unfinished merge", "--no-edit")
                                progress.console.print("  [green]✓[/green] Completed unfinished merge")
                                change_tracker.changes_to_commit.append("completed unfinished merge")
                            else:
                                # Still have unstaged changes, check if they're just unresolved conflicts
                                # Stage any changes in task files (they should be auto-resolved by now)
                                git_repo.git.add("tasks/")
                                git_repo.git.commit("-m", "Auto-sync: Completed unfinished merge", "--no-edit")
                                progress.console.print(
                                    "  [green]✓[/green] Completed unfinished merge with auto-staged changes"
                                )
                                change_tracker.changes_to_commit.append("completed unfinished merge")
                        except GitCommandError as e:
                            # Failed to complete merge
                            if "conflict" in str(e).lower() or "unmerged" in str(e).lower():
                                progress.console.print(
                                    "  [red]✗[/red] Cannot complete merge: unresolved conflicts remain"
                                )
                                progress.console.print(
                                    "  [red]→[/red] Please resolve conflicts manually with: git status"
                                )
                                # Skip this repository - don't try to proceed with sync
                                progress.update(overall_task, advance=1)
                                continue
                            else:
                                # Other error, try to abort the merge
                                progress.console.print(
                                    f"  [yellow]⚠[/yellow] Cannot complete merge, aborting... ({escape(str(e))})"
                                )
                                try:
                                    git_repo.git.merge("--abort")
                                    progress.console.print("  [green]✓[/green] Aborted unfinished merge")
                                except Exception:
                                    progress.console.print("  [red]✗[/red] Failed to abort merge")
                                    progress.console.print("  [red]→[/red] Please run: git merge --abort")
                                    # Skip this repository
                                    progress.update(overall_task, advance=1)
                                    continue

                    # Detect conflicts before pulling (pass cache to avoid redundant parsing)
                    def check_conflicts():
                        return detect_conflicts(git_repo, repository.path, task_cache=task_cache)

                    conflicts, _ = run_with_spinner(
                        progress, spinner_task, "Checking for conflicts", check_conflicts, verbose, operations_task
                    )

                    if conflicts:
                        progress.console.print(f"  [yellow]⚠[/yellow] Found {len(conflicts)} conflicting task(s)")
                        resolved_count = 0

                        for conflict in conflicts:
                            resolved_task = None

                            # Apply resolution strategy
                            if strategy == "local":
                                progress.console.print(f"    • {conflict.file_path.name}: Using local version")
                                resolved_task = conflict.local_task
                            elif strategy == "remote":
                                progress.console.print(f"    • {conflict.file_path.name}: Using remote version")
                                resolved_task = conflict.remote_task
                            elif strategy == "interactive":
                                # Stop progress display for interactive input
                                progress.stop()
                                try:
                                    resolved_task = resolve_conflict_interactive(conflict, config.default_editor)
                                finally:
                                    progress.start()
                            elif strategy == "auto" and auto_merge:
                                # Try smart merge
                                if conflict.can_auto_merge:
                                    resolved_task = smart_merge_tasks(
                                        conflict.local_task, conflict.remote_task, conflict.conflicting_fields
                                    )
                                    if resolved_task:
                                        # Show detailed merge information
                                        base_version = (
                                            "local"
                                            if conflict.local_task.modified >= conflict.remote_task.modified
                                            else "remote"
                                        )
                                        progress.console.print(
                                            f"    • {conflict.file_path.name}: Auto-merged (base: {base_version})"
                                        )

                                        # Show what was merged for each field
                                        _show_merge_details(
                                            progress.console,
                                            conflict.local_task,
                                            conflict.remote_task,
                                            conflict.conflicting_fields,
                                            base_version,
                                        )
                                    else:
                                        # Fall back to interactive
                                        progress.stop()
                                        try:
                                            resolved_task = resolve_conflict_interactive(
                                                conflict, config.default_editor
                                            )
                                        finally:
                                            progress.start()
                                else:
                                    # Requires manual resolution
                                    progress.stop()
                                    try:
                                        resolved_task = resolve_conflict_interactive(conflict, config.default_editor)
                                    finally:
                                        progress.start()
                            else:
                                # Default: interactive
                                progress.stop()
                                try:
                                    resolved_task = resolve_conflict_interactive(conflict, config.default_editor)
                                finally:
                                    progress.start()

                            # Save resolved task
                            if resolved_task:
                                repository.save_task(resolved_task)
                                # Invalidate cache since task was modified
                                task_cache.invalidate(repository.path / conflict.file_path)
                                git_repo.git.add(str(conflict.file_path))
                                resolved_count += 1

                        # Track conflict resolution (don't commit yet - will consolidate later)
                        if resolved_count > 0:
                            change_tracker.record_conflict_resolution(resolved_count)
                            progress.console.print(
                                f"  [green]✓[/green] Resolved and staged {resolved_count} conflict(s)"
                            )
                    else:
                        progress.console.print("  [green]✓[/green] No conflicts detected")

                    # Merge remote changes (we already fetched during conflict detection, so use merge not pull)
                    pull_succeeded = True
                    try:

                        def merge_changes():
                            # Get the remote branch name (usually origin/main or origin/master)
                            origin = git_repo.remotes.origin
                            remote_branch = origin.refs[0].name  # e.g., 'origin/main'
                            # Use merge instead of pull since we already fetched
                            # Note: git merge doesn't have --no-rebase flag (that's for pull)
                            git_repo.git.merge(remote_branch)

                        run_with_spinner(
                            progress, spinner_task, "Merging remote changes", merge_changes, verbose, operations_task
                        )
                    except Exception as e:
                        if "would be overwritten" in str(e) or "conflict" in str(e).lower():
                            pull_succeeded = False
                            progress.console.print("  [yellow]⚠[/yellow] Pull created conflicts")
                        else:
                            raise

                    # Mark that pull occurred (affects README generation decision)
                    if pull_succeeded:
                        change_tracker.record_pull()

                    # Check for conflict markers after pull
                    if not pull_succeeded or _has_conflict_markers(repository.path):

                        def resolve_markers():
                            return _resolve_conflict_markers(repository, progress.console, task_cache)

                        resolved_files, _ = run_with_spinner(
                            progress,
                            spinner_task,
                            "Resolving conflict markers",
                            resolve_markers,
                            verbose,
                            operations_task,
                        )

                        if resolved_files:
                            progress.console.print(
                                f"  [green]✓[/green] Auto-resolved {len(resolved_files)} conflicted file(s)"
                            )

                            # Stage resolved files (don't commit yet - will consolidate later)
                            def stage_resolutions():
                                for file_path in resolved_files:
                                    git_repo.git.add(str(file_path))

                            run_with_spinner(
                                progress,
                                spinner_task,
                                "Staging conflict resolutions",
                                stage_resolutions,
                                verbose,
                                operations_task,
                            )

                            change_tracker.record_marker_resolution(len(resolved_files))

                        # Resolve README conflicts (auto-generated files, safe to auto-resolve)
                        def resolve_readme():
                            return resolve_readme_conflicts(repository.path, progress.console)

                        resolved_readmes, _ = run_with_spinner(
                            progress,
                            spinner_task,
                            "Resolving README conflicts",
                            resolve_readme,
                            verbose,
                            operations_task,
                        )

                        if resolved_readmes:
                            # Stage resolved README files
                            def stage_readme_resolutions():
                                for file_path in resolved_readmes:
                                    git_repo.git.add(str(file_path.relative_to(repository.path)))

                            run_with_spinner(
                                progress,
                                spinner_task,
                                "Staging README resolutions",
                                stage_readme_resolutions,
                                verbose,
                                operations_task,
                            )

                    # Smart README generation - only regenerate if tasks may have changed
                    if change_tracker.should_regenerate_readme():

                        def generate_readme():
                            task_count = len(repository.list_tasks(include_archived=False))
                            repository.generate_readme(config)
                            return task_count

                        task_count, _ = run_with_spinner(
                            progress, spinner_task, "Updating README", generate_readme, verbose, operations_task
                        )
                        if verbose:
                            progress.console.print(f"    [dim]({task_count} tasks)[/dim]")

                        # Generate archive README with archived tasks
                        def generate_archive_readme():
                            repository.generate_archive_readme(config)

                        run_with_spinner(
                            progress,
                            spinner_task,
                            "Updating archive README",
                            generate_archive_readme,
                            verbose,
                            operations_task,
                        )

                        # Check if README was actually changed and stage it (don't commit yet)
                        if git_repo.is_dirty(untracked_files=True):

                            def stage_readme():
                                git_repo.git.add("README.md")
                                git_repo.git.add("tasks/archive/README.md")

                            run_with_spinner(
                                progress, spinner_task, "Staging README changes", stage_readme, verbose, operations_task
                            )

                            change_tracker.record_readme_change()
                    else:
                        progress.console.print("  [dim]→ Skipping README generation (no task changes)[/dim]")
                        if verbose:
                            progress.console.print("    [dim](Use sync with task changes to update README)[/dim]")

                    # Consolidated commit: Combine all staged changes into a single commit
                    if git_repo.is_dirty(index=True, working_tree=False, untracked_files=False):
                        # We have staged changes, create consolidated commit
                        def create_consolidated_commit():
                            commit_message = change_tracker.get_commit_message()
                            git_repo.index.commit(commit_message)

                        run_with_spinner(
                            progress,
                            spinner_task,
                            "Creating consolidated commit",
                            create_consolidated_commit,
                            verbose,
                            operations_task,
                        )
                    elif change_tracker.changes_to_commit:
                        # We tracked changes but nothing is staged (unusual, but possible)
                        progress.console.print("  [dim]→ No changes to commit[/dim]")

                    # Push changes
                    if push:

                        def push_changes():
                            origin = git_repo.remotes.origin
                            push_info = origin.push()

                            # Check if push failed by examining PushInfo flags
                            # GitPython doesn't always raise exceptions on push failures
                            for info in push_info:
                                # Check for error flags - IMPORTANT: Check REJECTED before ERROR
                                # because rejected pushes set both flags, but we want auto-recovery for REJECTED
                                if info.flags & info.REJECTED:
                                    # Non-fast-forward - will attempt auto-recovery
                                    raise GitCommandError("git push", "REJECTED")
                                if info.flags & info.REMOTE_REJECTED:
                                    raise GitCommandError("git push", f"Remote rejected push: {info.summary}")
                                if info.flags & info.REMOTE_FAILURE:
                                    raise GitCommandError("git push", f"Remote failure during push: {info.summary}")
                                if info.flags & info.ERROR:
                                    raise GitCommandError("git push", f"Push failed with ERROR flag: {info.summary}")

                            return push_info

                        try:
                            run_with_spinner(
                                progress, spinner_task, "Pushing to remote", push_changes, verbose, operations_task
                            )
                        except GitCommandError as e:
                            # Check if this is a non-fast-forward rejection that we can auto-recover
                            if "REJECTED" in str(e):
                                progress.console.print(
                                    "  [yellow]⚠[/yellow] Push rejected (branches diverged) - attempting auto-recovery..."
                                )

                                # Try to pull with rebase
                                try:

                                    def rebase_pull():
                                        # Get current branch
                                        current_branch = git_repo.active_branch.name
                                        # Pull with rebase to integrate remote changes
                                        git_repo.git.pull("--rebase", "origin", current_branch)

                                    run_with_spinner(
                                        progress,
                                        spinner_task,
                                        "Pulling with rebase",
                                        rebase_pull,
                                        verbose,
                                        operations_task,
                                    )

                                    # Check if rebase created conflicts
                                    if git_repo.is_dirty(working_tree=True, untracked_files=False):
                                        # Rebase created conflicts - abort and report
                                        progress.console.print(
                                            "  [red]✗[/red] Rebase created conflicts - aborting auto-recovery"
                                        )
                                        try:
                                            git_repo.git.rebase("--abort")
                                            progress.console.print("  [yellow]→[/yellow] Aborted rebase")
                                        except Exception:
                                            pass
                                        progress.console.print(
                                            "  [yellow]→[/yellow] Manual resolution required: git pull --rebase && git push"
                                        )
                                        raise
                                    else:
                                        # Rebase succeeded - try push again
                                        progress.console.print("  [green]✓[/green] Rebase successful - retrying push")

                                        def retry_push():
                                            repo_origin = git_repo.remotes.origin
                                            push_info = repo_origin.push()
                                            # Check for errors again
                                            for info in push_info:
                                                if info.flags & (
                                                    info.ERROR
                                                    | info.REJECTED
                                                    | info.REMOTE_REJECTED
                                                    | info.REMOTE_FAILURE
                                                ):
                                                    raise GitCommandError(
                                                        "git push", f"Push still failed: {info.summary}"
                                                    )
                                            return push_info

                                        run_with_spinner(
                                            progress, spinner_task, "Pushing to remote (retry)", retry_push, verbose
                                        )

                                except GitCommandError as rebase_error:
                                    # Rebase or retry push failed
                                    if "conflict" in str(rebase_error).lower():
                                        progress.console.print(
                                            "  [red]✗[/red] Auto-recovery failed: conflicts during rebase"
                                        )
                                        progress.console.print(
                                            "  [yellow]→[/yellow] Resolve manually: git pull --rebase && git push"
                                        )
                                    raise
                            else:
                                # Other push error - re-raise
                                raise
                else:
                    progress.console.print("  • No remote configured (local repository only)")

                    # For local repos, always regenerate README (no pull to track)
                    # But use same smart generation logic
                    change_tracker.record_pull()  # Simulate that "changes occurred" to trigger README generation

                    def generate_readme():
                        task_count = len(repository.list_tasks(include_archived=False))
                        repository.generate_readme(config)
                        return task_count

                    task_count, _ = run_with_spinner(
                        progress, spinner_task, "Updating README", generate_readme, verbose, operations_task
                    )
                    if verbose:
                        progress.console.print(f"    [dim]({task_count} tasks)[/dim]")

                    # Generate archive README with archived tasks
                    def generate_archive_readme():
                        repository.generate_archive_readme(config)

                    run_with_spinner(
                        progress,
                        spinner_task,
                        "Updating archive README",
                        generate_archive_readme,
                        verbose,
                        operations_task,
                    )

                    # Check if README was changed and stage it
                    if git_repo.is_dirty(untracked_files=True):

                        def stage_readme():
                            git_repo.git.add("README.md")
                            git_repo.git.add("tasks/archive/README.md")

                        run_with_spinner(
                            progress, spinner_task, "Staging README changes", stage_readme, verbose, operations_task
                        )

                        change_tracker.record_readme_change()

                    # Consolidated commit for local repo
                    if git_repo.is_dirty(index=True, working_tree=False, untracked_files=False):

                        def create_consolidated_commit():
                            commit_message = change_tracker.get_commit_message()
                            git_repo.index.commit(commit_message)

                        run_with_spinner(
                            progress,
                            spinner_task,
                            "Creating consolidated commit",
                            create_consolidated_commit,
                            verbose,
                            operations_task,
                        )

                # Record timing for this repository
                repo_elapsed = time.perf_counter() - repo_start_time
                repo_timings[repository.name] = repo_elapsed

                # Update overall progress
                if overall_task is not None:
                    progress.update(overall_task, advance=1)

            except GitCommandError as e:
                _log_sync_error(repository.name, e)
                progress.console.print(f"  [red]✗[/red] Git error: {escape(str(e))}", style="red")
                repo_timings[repository.name] = time.perf_counter() - repo_start_time
                if overall_task is not None:
                    progress.update(overall_task, advance=1)
                continue
            except Exception as e:
                _log_sync_error(repository.name, e)
                progress.console.print(f"  [red]✗[/red] Error: {escape(str(e))}", style="red")
                repo_timings[repository.name] = time.perf_counter() - repo_start_time
                if overall_task is not None:
                    progress.update(overall_task, advance=1)
                continue

    # Print timing summary
    total_elapsed = time.perf_counter() - total_start_time
    console.print()
    console.print("[bold green]✓ Sync completed[/bold green]")

    if verbose and repo_timings:
        console.print()
        console.print("[bold]Timing Summary:[/bold]")
        for repo_name, elapsed in repo_timings.items():
            console.print(f"  • {repo_name}: {elapsed:.1f}s")
        console.print(f"  [bold]Total: {total_elapsed:.1f}s[/bold]")

    console.print()

    # Display all non-archived tasks to show current state after sync
    all_tasks = manager.list_all_tasks(include_archived=False)

    if all_tasks:
        # Rebalance IDs to sequential order after sync
        from taskrepo.utils.id_mapping import save_id_cache
        from taskrepo.utils.sorting import sort_tasks

        sorted_tasks = sort_tasks(all_tasks, config, all_tasks=all_tasks)
        save_id_cache(sorted_tasks, rebalance=True)

        console.print("[cyan]IDs rebalanced to sequential order[/cyan]")
        console.print()

        display_tasks_table(all_tasks, config, save_cache=False)


def _show_merge_details(
    console: Console, local_task: Task, remote_task: Task, conflicting_fields: list[str], base_version: str
) -> None:
    """Display detailed information about how fields were merged.

    Args:
        console: Rich console for output
        local_task: Local task version
        remote_task: Remote task version
        conflicting_fields: List of conflicting field names
        base_version: Which version was used as base ("local" or "remote")
    """
    # Define field categories
    list_fields = {"assignees", "tags", "links", "depends"}
    priority_statuses = ["in-progress", "completed", "cancelled"]

    # Track merge strategies for display
    merge_info = []

    for field in conflicting_fields:
        if field in list_fields:
            # List fields are merged by union
            local_set = set(getattr(local_task, field))
            remote_set = set(getattr(remote_task, field))
            if local_set != remote_set:
                merge_info.append(f"{field}: union")
        elif field == "status":
            # Check if remote status has priority
            if remote_task.status in priority_statuses:
                merge_info.append(f"status: remote priority ({remote_task.status})")
            else:
                merge_info.append(f"status: {base_version}")
        else:
            # Simple fields use base version
            merge_info.append(f"{field}: {base_version}")

    if merge_info:
        for info in merge_info:
            console.print(f"      - {info}")


def _has_conflict_markers(repo_path: Path) -> bool:
    """Check if any task files contain git conflict markers.

    Args:
        repo_path: Path to repository

    Returns:
        True if conflict markers found, False otherwise
    """
    tasks_dir = repo_path / "tasks"
    if not tasks_dir.exists():
        return False

    for task_file in tasks_dir.rglob("task-*.md"):
        try:
            content = task_file.read_text()
            if "<<<<<<< HEAD" in content:
                return True
        except Exception:
            continue

    return False


def _resolve_conflict_markers(
    repository: Repository, console: Console, task_cache: "TaskCache | None" = None
) -> list[Path]:
    """Resolve git conflict markers in task files automatically.

    Parses conflicted files, extracts local and remote versions,
    uses smart merge (keep newer) to resolve, and saves resolved version.
    Falls back to keeping local version if parsing fails.

    Args:
        repository: Repository object
        console: Rich console for output
        task_cache: Optional TaskCache to avoid redundant parsing and invalidate on changes

    Returns:
        List of file paths that were resolved
    """
    resolved_files: list[Path] = []
    failed_files: list[Path] = []
    tasks_dir = repository.path / "tasks"

    if not tasks_dir.exists():
        return resolved_files

    for task_file in tasks_dir.rglob("task-*.md"):
        try:
            content = task_file.read_text()

            # Check for conflict markers
            if "<<<<<<< HEAD" not in content:
                continue

            # Parse the conflicted content
            local_task, remote_task = _parse_conflicted_file(content, task_file, repository.name)

            resolved_task = None
            resolution_method = ""

            if local_task and remote_task:
                # Use smart merge: prefer newer modified timestamp
                if local_task.modified >= remote_task.modified:
                    resolved_task = local_task
                    resolution_method = "local (newer)"
                else:
                    resolved_task = remote_task
                    resolution_method = "remote (newer)"
            elif local_task:
                # Only local version parsed successfully
                resolved_task = local_task
                resolution_method = "local (fallback)"
            elif remote_task:
                # Only remote version parsed successfully
                resolved_task = remote_task
                resolution_method = "remote (fallback)"
            else:
                # Neither version could be parsed - use simple marker removal fallback
                console.print(f"    [yellow]⚠[/yellow] Could not parse conflict in {task_file.name}")
                console.print("    [yellow]→[/yellow] Attempting fallback: keeping local version")

                # Try to extract just the local version by removing markers
                resolved_content = _extract_local_from_markers(content)
                if resolved_content and "<<<<<<< HEAD" not in resolved_content:
                    task_file.write_text(resolved_content)
                    resolved_files.append(task_file.relative_to(repository.path))
                    console.print(f"    • {task_file.name}: Kept local version (simple extraction)")
                    continue
                else:
                    # Complete failure - file needs manual resolution
                    failed_files.append(task_file)
                    console.print(f"    [red]✗[/red] Failed to auto-resolve {task_file.name}")
                    console.print("    [red]→[/red] Manual resolution required")
                    continue

            # Save resolved task
            if resolved_task:
                # Update modified timestamp
                resolved_task.modified = datetime.now()

                # Save and validate
                repository.save_task(resolved_task)

                # Invalidate cache since task was modified
                if task_cache:
                    task_cache.invalidate(task_file)

                # Verify conflict markers are gone
                verified_content = task_file.read_text()
                if "<<<<<<< HEAD" in verified_content:
                    console.print(f"    [red]✗[/red] Markers still present after save in {task_file.name}")
                    failed_files.append(task_file)
                    continue

                resolved_files.append(task_file.relative_to(repository.path))
                console.print(f"    • {task_file.name}: Using {resolution_method}")

        except Exception as e:
            console.print(f"    [red]✗[/red] Error resolving {task_file.name}: {escape(str(e))}")
            failed_files.append(task_file)
            continue

    # Report on failed files
    if failed_files:
        console.print()
        console.print(f"    [yellow]⚠[/yellow] {len(failed_files)} file(s) require manual resolution:")
        for failed_file in failed_files:
            console.print(f"      • {failed_file.name}")
        console.print("    [yellow]→[/yellow] Edit these files manually to remove conflict markers")

    return resolved_files


def _extract_local_from_markers(content: str) -> str | None:
    """Extract local version from conflict markers as fallback.

    Removes conflict markers and keeps only the local (HEAD) version.

    Args:
        content: File content with conflict markers

    Returns:
        Content with local version only, or None if extraction fails
    """
    try:
        # Use pre-compiled pattern to extract everything except the remote section
        result = CONFLICT_MARKER_EXTRACT_PATTERN.sub(r"\1\n", content)

        # Verify markers are removed
        if "<<<<<<< HEAD" not in result and "=======" not in result and ">>>>>>>" not in result:
            return result
        return None
    except Exception:
        return None


def _parse_conflicted_file(content: str, file_path: Path, repo_name: str) -> tuple[Task | None, Task | None]:
    """Parse a file with git conflict markers into local and remote task objects.

    Args:
        content: File content with conflict markers
        file_path: Path to the file
        repo_name: Repository name

    Returns:
        Tuple of (local_task, remote_task) or (None, None) if parsing fails
    """
    try:
        # Extract task ID from filename
        task_id = file_path.stem.replace("task-", "")

        # Use pre-compiled pattern to split by conflict markers
        match = CONFLICT_MARKER_PATTERN.search(content)

        if not match:
            # Try alternative pattern without strict newline requirements
            match = CONFLICT_MARKER_ALT_PATTERN.search(content)
            if not match:
                return None, None

        local_section = match.group(1).strip()
        remote_section = match.group(2).strip()

        # Get the parts before and after the conflict
        before_conflict = content[: match.start()]
        after_match = re.search(r">>>>>>> [^\n]*\n?", content[match.start() :])
        after_conflict = content[match.start() + after_match.end() :] if after_match else ""

        # Reconstruct full local and remote versions
        local_content = before_conflict + local_section + "\n" + after_conflict
        remote_content = before_conflict + remote_section + "\n" + after_conflict

        # Parse as Task objects
        local_task = Task.from_markdown(local_content, task_id=task_id, repo=repo_name)
        remote_task = Task.from_markdown(remote_content, task_id=task_id, repo=repo_name)

        return local_task, remote_task

    except Exception as e:
        # Log the actual error for debugging
        console.print(f"    [dim]Debug: Failed to parse {file_path.name}: {str(e)}[/dim]")
        return None, None
