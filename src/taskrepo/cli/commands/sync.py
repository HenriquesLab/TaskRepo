"""Sync command for git operations."""

import click
from git import GitCommandError

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table


@click.command()
@click.option("--repo", "-r", help="Repository name (will sync all repos if not specified)")
@click.option("--push/--no-push", default=True, help="Push changes to remote")
@click.pass_context
def sync(ctx, repo, push):
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
