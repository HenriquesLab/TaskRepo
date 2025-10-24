"""Sync command for git operations."""

import click
from git import GitCommandError

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.conflict_resolver import resolve_conflict_interactive
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.merge import detect_conflicts, smart_merge_tasks


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
@click.pass_context
def sync(ctx, repo, push, auto_merge, strategy):
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

    for repository in repositories:
        git_repo = repository.git_repo

        # Display repository with URL or local path
        if git_repo.remotes:
            remote_url = git_repo.remotes.origin.url
            click.echo(f"\nSyncing repository: {repository.name} ({remote_url})")
        else:
            click.echo(f"\nSyncing repository: {repository.name} (local: {repository.path})")

        try:
            # Check if there are uncommitted changes (including untracked files)
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
                        resolved_task = None

                        # Apply resolution strategy
                        if strategy == "local":
                            click.echo(f"    • {conflict.file_path.name}: Using local version")
                            resolved_task = conflict.local_task
                        elif strategy == "remote":
                            click.echo(f"    • {conflict.file_path.name}: Using remote version")
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
                                    click.echo(f"    • {conflict.file_path.name}: Auto-merged (using newer timestamp)")
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
                        click.secho(f"  ✓ Resolved and committed {resolved_count} conflict(s)", fg="green")
                else:
                    click.secho("  ✓ No conflicts detected", fg="green")

                # Pull changes
                click.echo("  • Pulling from remote...")
                origin = git_repo.remotes.origin
                origin.pull()
                click.secho("  ✓ Pulled from remote", fg="green")

                # Generate README with active tasks
                click.echo("  • Updating README...")
                repository.generate_readme(config)
                click.secho("  ✓ README updated", fg="green")

                # Generate done README with completed tasks
                click.echo("  • Updating done archive README...")
                repository.generate_done_readme(config)
                click.secho("  ✓ Done README updated", fg="green")

                # Check if README was changed and commit it
                if git_repo.is_dirty(untracked_files=True):
                    git_repo.git.add("README.md")
                    git_repo.git.add("tasks/done/README.md")
                    git_repo.index.commit("Auto-update: README with active and completed tasks")
                    click.secho("  ✓ README changes committed", fg="green")

                # Push changes
                if push:
                    click.echo("  • Pushing to remote...")
                    origin.push()
                    click.secho("  ✓ Pushed to remote", fg="green")
            else:
                click.echo("  • No remote configured (local repository only)")

                # Generate README for local repo
                click.echo("  • Updating README...")
                repository.generate_readme(config)
                click.secho("  ✓ README updated", fg="green")

                # Generate done README with completed tasks
                click.echo("  • Updating done archive README...")
                repository.generate_done_readme(config)
                click.secho("  ✓ Done README updated", fg="green")

                # Check if README was changed and commit it
                if git_repo.is_dirty(untracked_files=True):
                    git_repo.git.add("README.md")
                    git_repo.git.add("tasks/done/README.md")
                    git_repo.index.commit("Auto-update: README with active and completed tasks")
                    click.secho("  ✓ README changes committed", fg="green")

        except GitCommandError as e:
            click.secho(f"  ✗ Git error: {e}", fg="red", err=True)
            continue
        except Exception as e:
            click.secho(f"  ✗ Error: {e}", fg="red", err=True)
            continue

    click.echo()
    click.secho("✓ Sync completed", fg="green")
    click.echo()

    # Display all active tasks to show current state after sync
    all_tasks = manager.list_all_tasks()
    active_tasks = [t for t in all_tasks if t.status != "completed"]

    if active_tasks:
        display_tasks_table(active_tasks, config, save_cache=True)
