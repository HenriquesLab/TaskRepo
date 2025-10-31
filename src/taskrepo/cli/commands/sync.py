"""Sync command for git operations."""

import re
import time
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
from taskrepo.utils.merge import detect_conflicts, smart_merge_tasks

console = Console()


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

                    def commit_changes():
                        git_repo.git.add(A=True)
                        git_repo.index.commit("Auto-commit: TaskRepo sync")

                    run_with_spinner(
                        progress, spinner_task, "Committing local changes", commit_changes, verbose, operations_task
                    )

                # Check if remote exists
                if git_repo.remotes:
                    # Detect conflicts before pulling
                    def check_conflicts():
                        return detect_conflicts(git_repo, repository.path)

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
                                        progress.console.print(
                                            f"    • {conflict.file_path.name}: Auto-merged (using newer timestamp)"
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
                                git_repo.git.add(str(conflict.file_path))
                                resolved_count += 1

                        # Commit resolved conflicts
                        if resolved_count > 0:
                            git_repo.index.commit(f"Merge: Resolved {resolved_count} task conflict(s)")
                            progress.console.print(
                                f"  [green]✓[/green] Resolved and committed {resolved_count} conflict(s)"
                            )
                    else:
                        progress.console.print("  [green]✓[/green] No conflicts detected")

                    # Pull changes
                    pull_succeeded = True
                    try:

                        def pull_changes():
                            origin = git_repo.remotes.origin
                            # Use --rebase=false to handle divergent branches
                            git_repo.git.pull("--rebase=false", "origin", git_repo.active_branch.name)

                        run_with_spinner(
                            progress, spinner_task, "Pulling from remote", pull_changes, verbose, operations_task
                        )
                    except Exception as e:
                        if "would be overwritten" in str(e) or "conflict" in str(e).lower():
                            pull_succeeded = False
                            progress.console.print("  [yellow]⚠[/yellow] Pull created conflicts")
                        else:
                            raise

                    # Check for conflict markers after pull
                    if not pull_succeeded or _has_conflict_markers(repository.path):

                        def resolve_markers():
                            return _resolve_conflict_markers(repository, progress.console)

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

                            def commit_resolutions():
                                for file_path in resolved_files:
                                    git_repo.git.add(str(file_path))
                                git_repo.index.commit(f"Auto-resolve: Fixed {len(resolved_files)} conflict marker(s)")

                            run_with_spinner(
                                progress,
                                spinner_task,
                                "Committing conflict resolutions",
                                commit_resolutions,
                                verbose,
                                operations_task,
                            )

                    # Generate README with all tasks
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

                    # Check if README was changed and commit it
                    if git_repo.is_dirty(untracked_files=True):

                        def commit_readme():
                            git_repo.git.add("README.md")
                            git_repo.git.add("tasks/archive/README.md")
                            git_repo.index.commit("Auto-update: README with tasks and archive")

                        run_with_spinner(
                            progress, spinner_task, "Committing README changes", commit_readme, verbose, operations_task
                        )

                    # Push changes
                    if push:

                        def push_changes():
                            origin = git_repo.remotes.origin
                            origin.push()

                        run_with_spinner(
                            progress, spinner_task, "Pushing to remote", push_changes, verbose, operations_task
                        )
                else:
                    progress.console.print("  • No remote configured (local repository only)")

                    # Generate README for local repo
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

                    # Check if README was changed and commit it
                    if git_repo.is_dirty(untracked_files=True):

                        def commit_readme():
                            git_repo.git.add("README.md")
                            git_repo.git.add("tasks/archive/README.md")
                            git_repo.index.commit("Auto-update: README with tasks and archive")

                        run_with_spinner(
                            progress, spinner_task, "Committing README changes", commit_readme, verbose, operations_task
                        )

                # Record timing for this repository
                repo_elapsed = time.perf_counter() - repo_start_time
                repo_timings[repository.name] = repo_elapsed

                # Update overall progress
                if overall_task is not None:
                    progress.update(overall_task, advance=1)

            except GitCommandError as e:
                progress.console.print(f"  [red]✗[/red] Git error: {escape(str(e))}", style="red")
                repo_timings[repository.name] = time.perf_counter() - repo_start_time
                if overall_task is not None:
                    progress.update(overall_task, advance=1)
                continue
            except Exception as e:
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

        sorted_tasks = sort_tasks(all_tasks, config)
        save_id_cache(sorted_tasks, rebalance=True)

        console.print("[cyan]IDs rebalanced to sequential order[/cyan]")
        console.print()

        display_tasks_table(all_tasks, config, save_cache=False)


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


def _resolve_conflict_markers(repository: Repository, console: Console) -> list[Path]:
    """Resolve git conflict markers in task files automatically.

    Parses conflicted files, extracts local and remote versions,
    uses smart merge (keep newer) to resolve, and saves resolved version.
    Falls back to keeping local version if parsing fails.

    Args:
        repository: Repository object
        console: Rich console for output

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
        # Pattern to extract everything except the remote section
        # Matches: <<<<<<< HEAD\n{local}\n=======\n{remote}\n>>>>>>> {commit}
        pattern = r"<<<<<<< HEAD\s*\n(.*?)\n=======\s*\n.*?\n>>>>>>> [^\n]*\n?"
        result = re.sub(pattern, r"\1\n", content, flags=re.DOTALL)

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

        # Split by conflict markers
        # Pattern: <<<<<<< HEAD\n{local}\n=======\n{remote}\n>>>>>>> {commit}
        # More flexible pattern to handle various formats
        pattern = r"<<<<<<< HEAD\s*\n(.*?)\n=======\s*\n(.*?)\n>>>>>>> [^\n]*"
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            # Try alternative pattern without strict newline requirements
            pattern_alt = r"<<<<<<< HEAD(.*?)=======(.*?)>>>>>>> "
            match = re.search(pattern_alt, content, re.DOTALL)
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
