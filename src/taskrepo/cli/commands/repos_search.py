"""Search for TaskRepo repositories on GitHub."""

import click
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import checkboxlist_dialog, confirm
from rich.console import Console
from rich.table import Table

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils.github import (
    GitHubError,
    check_gh_auth,
    check_gh_cli_installed,
    clone_github_repo,
    get_gh_install_message,
    list_github_repos,
)


@click.command(name="repos-search")
@click.argument("org", required=False)
@click.option("--list-only", is_flag=True, help="List repositories without prompting to clone")
@click.pass_context
def repos_search(ctx, org, list_only):
    r"""Search for TaskRepo repositories on GitHub.

    Searches for repositories matching the 'tasks-*' pattern in the specified
    GitHub organization or user. Shows which repositories are already cloned
    locally and allows you to clone new ones.

    \b
    Examples:
      tsk repos-search myorg              # Search in myorg
      tsk repos-search                    # Use default org from config
      tsk repos-search myorg --list-only  # Just list, don't prompt to clone
    """
    config = ctx.obj["config"]
    console = Console()

    # Check prerequisites early
    if not check_gh_cli_installed():
        click.secho("✗ GitHub CLI (gh) is not installed.", fg="red", err=True)
        click.echo()
        click.echo(get_gh_install_message())
        click.echo()
        click.echo("The repos-search command requires gh CLI to search for repositories on GitHub.")
        ctx.exit(1)

    if not check_gh_auth():
        click.secho("✗ Not authenticated with GitHub.", fg="red", err=True)
        click.echo()
        click.echo("To use the repos-search command, you need to authenticate with GitHub.")
        click.echo()
        click.echo("Steps:")
        click.echo("  1. Check your authentication status:")
        click.secho("     gh auth status", fg="cyan")
        click.echo()
        click.echo("  2. If not authenticated, run:")
        click.secho("     gh auth login", fg="cyan")
        click.echo()
        ctx.exit(1)

    # Determine organization to search
    if not org:
        org = config.default_github_org
        if not org:
            # Prompt user for organization
            click.echo("No GitHub organization specified.")
            click.echo("\nYou can:")
            click.echo("  • Enter an organization name below")
            click.echo("  • Run: tsk repos-search <org>")
            click.echo("  • Set a default: run 'tsk config' and choose option 7")
            click.echo()

            try:
                org = prompt("Enter GitHub organization/owner (or press Enter to cancel): ")
                org = org.strip()

                if not org:
                    click.echo("Cancelled.")
                    ctx.exit(0)

                # Ask if user wants to save as default
                if confirm("\nSave this as your default GitHub organization?"):
                    config.default_github_org = org
                    click.secho(f"✓ Saved '{org}' as default GitHub organization", fg="green")

            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")
                ctx.exit(0)

    # Try to list repositories
    try:
        click.echo(f"Searching for TaskRepo repositories in {org}...")
        repos = list_github_repos(org, pattern="tasks-*")
    except GitHubError as e:
        click.secho(f"\nError: {e}", fg="red", err=True)
        ctx.exit(1)

    if not repos:
        click.echo(f"\nNo TaskRepo repositories found in {org}.")
        click.echo("TaskRepo repositories should be named with the 'tasks-' prefix.")
        return

    # Get local repositories
    manager = RepositoryManager(config.parent_dir)
    local_repos = manager.discover_repositories()
    local_repo_names = {f"tasks-{repo.name}" for repo in local_repos}

    # Build status for each repo
    repo_info = []
    for repo in repos:
        repo_name = repo["name"]
        repo_url = repo["url"]
        is_cloned = repo_name in local_repo_names

        # Extract short name (remove 'tasks-' prefix)
        short_name = repo_name[6:] if repo_name.startswith("tasks-") else repo_name

        repo_info.append(
            {
                "name": repo_name,
                "short_name": short_name,
                "url": repo_url,
                "is_cloned": is_cloned,
            }
        )

    # Display results in a Rich table
    table = Table(title=f"\nTaskRepo Repositories in {org}", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="bold")
    table.add_column("Status", width=12)
    table.add_column("URL", style="dim")

    for idx, info in enumerate(repo_info, 1):
        status = "[green]✓ cloned[/green]" if info["is_cloned"] else "[yellow]✗ remote[/yellow]"
        table.add_row(str(idx), info["short_name"], status, info["url"])

    console.print(table)

    # Show summary
    cloned_count = sum(1 for r in repo_info if r["is_cloned"])
    remote_count = len(repo_info) - cloned_count
    click.echo(f"\nFound {len(repo_info)} repositories ({cloned_count} cloned, {remote_count} remote-only)")

    # Exit if list-only mode
    if list_only:
        return

    # Filter to only remote (not yet cloned) repos
    remote_repos = [r for r in repo_info if not r["is_cloned"]]

    if not remote_repos:
        click.echo("\nAll repositories are already cloned locally.")
        return

    # Prompt to clone
    click.echo()
    try:
        if not confirm("Would you like to clone any repositories?"):
            click.echo("Cancelled.")
            return
    except (KeyboardInterrupt, EOFError):
        click.echo("\nCancelled.")
        return

    # Show interactive checkbox selection
    click.echo()
    choices = [(r["short_name"], r["short_name"]) for r in remote_repos]

    try:
        # Use checkboxlist_dialog for multi-select
        selected = checkboxlist_dialog(
            title="Select repositories to clone",
            text="Use space to select/deselect, Enter to confirm:",
            values=choices,
        ).run()

        if not selected:
            click.echo("No repositories selected.")
            return

    except (KeyboardInterrupt, EOFError):
        click.echo("\nCancelled.")
        return

    # Clone selected repositories
    click.echo()
    success_count = 0
    failed_count = 0

    for short_name in selected:
        # Find the full repo info
        repo = next(r for r in remote_repos if r["short_name"] == short_name)
        repo_name = repo["name"]
        target_path = config.parent_dir / repo_name

        click.echo(f"Cloning {repo_name}...")

        try:
            clone_github_repo(org, repo_name, target_path)
            click.secho(f"  ✓ Successfully cloned to {target_path}", fg="green")
            success_count += 1
        except GitHubError as e:
            click.secho(f"  ✗ Failed: {e}", fg="red")
            failed_count += 1
        except Exception as e:
            click.secho(f"  ✗ Error: {e}", fg="red")
            failed_count += 1

    # Show summary
    click.echo()
    if success_count > 0:
        click.secho(
            f"✓ Successfully cloned {success_count} repositor{'y' if success_count == 1 else 'ies'}", fg="green"
        )
    if failed_count > 0:
        click.secho(f"✗ Failed to clone {failed_count} repositor{'y' if failed_count == 1 else 'ies'}", fg="red")
