"""Sync command for git operations."""

import click
from git import GitCommandError

from taskrepo.core.repository import RepositoryManager


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
        click.echo(f"\nSyncing repository: {repository.name}")

        git_repo = repository.git_repo

        try:
            # Check if there are uncommitted changes
            if git_repo.is_dirty():
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

                # Push changes
                if push:
                    click.echo("  • Pushing to remote...")
                    origin.push()
                    click.secho("  ✓ Pushed to remote", fg="green")
            else:
                click.echo("  • No remote configured (local repository only)")

        except GitCommandError as e:
            click.secho(f"  ✗ Git error: {e}", fg="red", err=True)
            continue
        except Exception as e:
            click.secho(f"  ✗ Error: {e}", fg="red", err=True)
            continue

    click.echo()
    click.secho("✓ Sync completed", fg="green")
