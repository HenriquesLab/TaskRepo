"""Sync command for git operations."""

import time

import click
from git import GitCommandError
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn

from taskrepo.core.repository import RepositoryManager
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
):
    """Run an operation with a spinner and timing."""
    start_time = time.perf_counter()
    progress.update(spinner_task, description=f"[cyan]{operation_name}...")

    try:
        result = operation_func()
        elapsed = time.perf_counter() - start_time

        if verbose:
            progress.console.print(f"  [green]✓[/green] {operation_name} [dim]({elapsed:.1f}s)[/dim]")
        else:
            progress.console.print(f"  [green]✓[/green] {operation_name}")

        return result, elapsed
    except Exception:
        elapsed = time.perf_counter() - start_time
        if verbose:
            progress.console.print(f"  [red]✗[/red] {operation_name} [dim]({elapsed:.1f}s)[/dim]")
        else:
            progress.console.print(f"  [red]✗[/red] {operation_name}")
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

    # Create progress context with overall repository progress and spinner
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn() if len(repositories) > 1 else TextColumn(""),
        TextColumn("[progress.percentage]{task.completed}/{task.total}") if len(repositories) > 1 else TextColumn(""),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        # Add overall progress task (only if multiple repositories)
        if len(repositories) > 1:
            overall_task = progress.add_task("[bold]Syncing repositories", total=len(repositories), completed=0)
        else:
            overall_task = None

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

                    run_with_spinner(progress, spinner_task, "Committing local changes", commit_changes, verbose)

                # Check if remote exists
                if git_repo.remotes:
                    # Detect conflicts before pulling
                    def check_conflicts():
                        return detect_conflicts(git_repo, repository.path)

                    conflicts, _ = run_with_spinner(
                        progress, spinner_task, "Checking for conflicts", check_conflicts, verbose
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
                                resolved_task = resolve_conflict_interactive(conflict, config.default_editor)
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
                                        resolved_task = resolve_conflict_interactive(conflict, config.default_editor)
                                else:
                                    # Requires manual resolution
                                    resolved_task = resolve_conflict_interactive(conflict, config.default_editor)
                            else:
                                # Default: interactive
                                resolved_task = resolve_conflict_interactive(conflict, config.default_editor)

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
                    def pull_changes():
                        origin = git_repo.remotes.origin
                        # Use --rebase=false to handle divergent branches
                        git_repo.git.pull("--rebase=false", "origin", git_repo.active_branch.name)

                    run_with_spinner(progress, spinner_task, "Pulling from remote", pull_changes, verbose)

                    # Generate README with all tasks
                    def generate_readme():
                        task_count = len(repository.list_tasks(include_archived=False))
                        repository.generate_readme(config)
                        return task_count

                    task_count, _ = run_with_spinner(
                        progress, spinner_task, "Updating README", generate_readme, verbose
                    )
                    if verbose:
                        progress.console.print(f"    [dim]({task_count} tasks)[/dim]")

                    # Generate archive README with archived tasks
                    def generate_archive_readme():
                        repository.generate_archive_readme(config)

                    run_with_spinner(
                        progress, spinner_task, "Updating archive README", generate_archive_readme, verbose
                    )

                    # Check if README was changed and commit it
                    if git_repo.is_dirty(untracked_files=True):

                        def commit_readme():
                            git_repo.git.add("README.md")
                            git_repo.git.add("tasks/archive/README.md")
                            git_repo.index.commit("Auto-update: README with tasks and archive")

                        run_with_spinner(progress, spinner_task, "Committing README changes", commit_readme, verbose)

                    # Push changes
                    if push:

                        def push_changes():
                            origin = git_repo.remotes.origin
                            origin.push()

                        run_with_spinner(progress, spinner_task, "Pushing to remote", push_changes, verbose)
                else:
                    progress.console.print("  • No remote configured (local repository only)")

                    # Generate README for local repo
                    def generate_readme():
                        task_count = len(repository.list_tasks(include_archived=False))
                        repository.generate_readme(config)
                        return task_count

                    task_count, _ = run_with_spinner(
                        progress, spinner_task, "Updating README", generate_readme, verbose
                    )
                    if verbose:
                        progress.console.print(f"    [dim]({task_count} tasks)[/dim]")

                    # Generate archive README with archived tasks
                    def generate_archive_readme():
                        repository.generate_archive_readme(config)

                    run_with_spinner(
                        progress, spinner_task, "Updating archive README", generate_archive_readme, verbose
                    )

                    # Check if README was changed and commit it
                    if git_repo.is_dirty(untracked_files=True):

                        def commit_readme():
                            git_repo.git.add("README.md")
                            git_repo.git.add("tasks/archive/README.md")
                            git_repo.index.commit("Auto-update: README with tasks and archive")

                        run_with_spinner(progress, spinner_task, "Committing README changes", commit_readme, verbose)

                # Record timing for this repository
                repo_elapsed = time.perf_counter() - repo_start_time
                repo_timings[repository.name] = repo_elapsed

                # Update overall progress
                if overall_task is not None:
                    progress.update(overall_task, advance=1)

            except GitCommandError as e:
                progress.console.print(f"  [red]✗[/red] Git error: {e}", style="red")
                repo_timings[repository.name] = time.perf_counter() - repo_start_time
                if overall_task is not None:
                    progress.update(overall_task, advance=1)
                continue
            except Exception as e:
                progress.console.print(f"  [red]✗[/red] Error: {e}", style="red")
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
