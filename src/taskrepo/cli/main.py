"""Main CLI entry point for TaskRepo."""

import click

from taskrepo.__version__ import __version__
from taskrepo.cli.commands.add import add
from taskrepo.cli.commands.config import config_cmd
from taskrepo.cli.commands.delete import delete
from taskrepo.cli.commands.done import done
from taskrepo.cli.commands.edit import edit
from taskrepo.cli.commands.extend import ext
from taskrepo.cli.commands.info import info
from taskrepo.cli.commands.list import list_tasks
from taskrepo.cli.commands.repos_search import repos_search
from taskrepo.cli.commands.search import search
from taskrepo.cli.commands.sync import sync
from taskrepo.core.config import Config
from taskrepo.utils.update_checker import check_and_notify_updates


class OrderedGroup(click.Group):
    """Custom Click Group that displays commands in sections."""

    def format_commands(self, ctx, formatter):
        """Format commands with section headers."""
        # Define command sections in desired order
        sections = [
            (
                "Setup & Configuration",
                ["init", "create-repo", "config", "config-show"],
            ),
            (
                "Viewing Tasks",
                ["list", "search", "info"],
            ),
            (
                "Managing Tasks",
                ["add", "edit", "ext", "done", "del"],
            ),
            (
                "Repository Operations",
                ["repos", "repos-search", "sync"],
            ),
        ]

        # Build command dict
        commands = {}
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None:
                continue
            if cmd.hidden:
                continue
            commands[subcommand] = cmd

        # Format each section
        for section_name, command_names in sections:
            # Filter commands that exist in this section
            section_commands = [(name, commands[name]) for name in command_names if name in commands]

            if section_commands:
                with formatter.section(section_name):
                    formatter.write_dl(
                        [(name, cmd.get_short_help_str(limit=formatter.width)) for name, cmd in section_commands]
                    )


@click.group(cls=OrderedGroup)
@click.version_option(version=__version__, prog_name="taskrepo")
@click.pass_context
def cli(ctx):
    """TaskRepo - TaskWarrior-inspired task management with git and markdown.

    Manage your tasks as markdown files in git repositories.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Load configuration
    ctx.obj["config"] = Config()


@cli.result_callback()
@click.pass_context
def process_result(ctx, result, **kwargs):
    """Process result after command execution.

    This runs after any command completes and checks for updates.
    """
    # Check for updates after command completes
    check_and_notify_updates()


# Register commands
cli.add_command(add)
cli.add_command(config_cmd)
cli.add_command(list_tasks)
cli.add_command(edit)
cli.add_command(done)
cli.add_command(delete, name="del")  # Register only as "del"
cli.add_command(ext)
cli.add_command(info)
cli.add_command(repos_search)
cli.add_command(search)
cli.add_command(sync)


@cli.command()
@click.option("--reconfigure", is_flag=True, help="Reconfigure even if already initialized")
@click.pass_context
def init(ctx, reconfigure):
    """Initialize TaskRepo configuration."""
    from pathlib import Path

    from prompt_toolkit import prompt
    from prompt_toolkit.shortcuts import confirm

    from taskrepo.core.repository import RepositoryManager

    config = ctx.obj["config"]

    click.secho("TaskRepo Initialization", fg="cyan", bold=True)
    click.echo()

    # Check if already configured
    config_exists = config.config_path.exists()
    if config_exists and not reconfigure:
        click.echo(f"Configuration file: {config.config_path}")
        click.echo(f"Parent directory: {config.parent_dir}")
        click.echo()

        if not confirm("Reconfigure TaskRepo?", default=False):
            # Just verify setup
            manager = RepositoryManager(config.parent_dir)
            repos = manager.discover_repositories()

            if repos:
                click.echo()
                click.secho(f"✓ Found {len(repos)} repositor{'y' if len(repos) == 1 else 'ies'}:", fg="green")
                for repo in repos:
                    task_count = len(repo.list_tasks())
                    click.echo(f"  - {repo.name} ({task_count} tasks)")
            else:
                click.echo()
                click.secho("⚠ No repositories found.", fg="yellow")
                click.echo("  Create one with: tsk create-repo")

            return

        click.echo()

    # Scan for existing repositories
    click.echo("Scanning for existing task repositories...")
    current_dir = Path.cwd()

    # Scan current directory and parent
    scan_locations = [current_dir]
    if current_dir.parent != current_dir:  # Not at root
        scan_locations.append(current_dir.parent)

    # Also scan common code directories
    home = Path.home()
    for common_dir in ["Code", "GitHub", "Projects", "Documents", "src"]:
        potential_path = home / common_dir
        if potential_path.exists() and potential_path not in scan_locations:
            scan_locations.append(potential_path)

    # Find all locations with task repositories
    found_locations = {}
    for location in scan_locations:
        repos_dict = RepositoryManager.scan_for_task_repositories(location, max_depth=2)
        found_locations.update(repos_dict)

    # Present options to user
    parent_dir = None

    if found_locations:
        click.secho(f"✓ Found task repositories in {len(found_locations)} location(s):", fg="green")
        click.echo()

        # Sort by number of repos (descending)
        sorted_locations = sorted(found_locations.items(), key=lambda x: len(x[1]), reverse=True)

        for idx, (location, repos) in enumerate(sorted_locations, 1):
            click.echo(f"  {idx}. {location}")
            for repo_name in repos:
                click.echo(f"     - tasks-{repo_name}")
        click.echo()

        # If current directory has repos, offer it as default
        if current_dir in found_locations:
            if confirm(f"Use current directory ({current_dir}) as parent?", default=True):
                parent_dir = current_dir
        elif found_locations:
            # Ask user to choose
            try:
                choice = prompt(f"Select location [1-{len(sorted_locations)}] or press Enter to specify custom path: ")
                choice = choice.strip()

                if choice:
                    try:
                        choice_idx = int(choice)
                        if 1 <= choice_idx <= len(sorted_locations):
                            parent_dir = sorted_locations[choice_idx - 1][0]
                    except ValueError:
                        click.secho("Invalid choice. Please specify custom path.", fg="yellow")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")
                ctx.exit(0)

    # If no parent_dir selected yet, ask for custom path
    if parent_dir is None:
        if not found_locations:
            click.echo("No existing task repositories found.")
            click.echo()

        default_path = str(current_dir) if not config_exists else str(config.parent_dir)

        try:
            custom_path = prompt(f"Enter parent directory path [{default_path}]: ", default=default_path)
            parent_dir = Path(custom_path.strip()).expanduser()
        except (KeyboardInterrupt, EOFError):
            click.echo("\nCancelled.")
            ctx.exit(0)

    # Save configuration
    config.parent_dir = parent_dir

    click.echo()
    click.secho(f"✓ Configuration saved to {config.config_path}", fg="green")
    click.secho(f"✓ Parent directory: {parent_dir}", fg="green")

    # Create directory if needed
    if not parent_dir.exists():
        if confirm(f"\nCreate directory {parent_dir}?", default=True):
            parent_dir.mkdir(parents=True, exist_ok=True)
            click.secho(f"✓ Created {parent_dir}", fg="green")

    # Verify setup by discovering repositories
    manager = RepositoryManager(parent_dir)
    repos = manager.discover_repositories()

    click.echo()
    if repos:
        click.secho(f"Found {len(repos)} repositor{'y' if len(repos) == 1 else 'ies'}:", fg="green")
        for repo in repos:
            task_count = len(repo.list_tasks())
            click.echo(f"  - {repo.name} ({task_count} tasks)")
        click.echo()
        click.secho("✓ Ready to use! Try: tsk list", fg="green", bold=True)
    else:
        click.secho("No repositories found in parent directory.", fg="yellow")
        click.echo()
        click.echo("Get started with:")
        click.echo("  • Create a new repository: tsk create-repo")
        click.echo("  • Clone existing repository: gh repo clone <org/repo> <local-path>")


@cli.command()
@click.option("--name", "-n", help="Repository name (will be prefixed with 'tasks-')")
@click.option("--github", is_flag=True, help="Create GitHub repository")
@click.option("-o", "--org", help="GitHub organization/owner (required with --github)")
@click.option("--interactive/--no-interactive", "-i/-I", default=True, help="Use interactive mode")
@click.pass_context
def create_repo(ctx, name, github, org, interactive):
    """Create a new task repository."""
    from taskrepo.core.repository import Repository, RepositoryManager
    from taskrepo.tui import prompts
    from taskrepo.utils.github import GitHubError, check_github_repo_exists, clone_github_repo

    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Interactive mode
    if interactive:
        click.echo("Creating a new task repository...\n")
        click.echo("Note: Repository names will be automatically prefixed with 'tasks-'")
        click.echo("(e.g., entering 'work' will create 'tasks-work')\n")

        # Get repository name
        if not name:
            # Get existing repo names for validation
            existing_repos = manager.discover_repositories()
            existing_names = [repo.name for repo in existing_repos]
            name = prompts.prompt_repo_name(existing_names=existing_names)
            if not name:
                click.echo("Cancelled.")
                ctx.exit(0)

        # Ask about GitHub integration
        if github is False:  # Only prompt if not explicitly set via flag
            github = prompts.prompt_github_enabled()

        # Handle GitHub integration
        visibility = None
        if github:
            # Get organization if not provided
            if not org:
                # Use default from config if available
                default_org = config.default_github_org
                # Get existing orgs from repos for autocomplete
                existing_orgs = manager.get_github_orgs()
                org = prompts.prompt_github_org(default=default_org, existing_orgs=existing_orgs)
                if not org:
                    click.echo("Cancelled.")
                    ctx.exit(0)

            # Get visibility
            visibility = prompts.prompt_visibility()

            # Check if GitHub repo already exists
            if check_github_repo_exists(org, f"tasks-{name}"):
                click.echo()
                click.secho(f"⚠️  Repository tasks-{name} already exists on GitHub!", fg="yellow", bold=True)
                click.echo(f"    URL: https://github.com/{org}/tasks-{name}")
                click.echo()

                # Ask if user wants to clone it
                from prompt_toolkit.shortcuts import confirm

                try:
                    if confirm("Would you like to clone it instead?"):
                        # Clone the repository
                        repo_path = config.parent_dir / f"tasks-{name}"
                        click.echo("\nCloning repository from GitHub...")

                        try:
                            clone_github_repo(org, f"tasks-{name}", repo_path)
                            repo = Repository(repo_path)
                            click.echo()
                            click.secho(f"✓ Cloned repository: {repo.name} at {repo.path}", fg="green")
                            click.secho(f"✓ GitHub repository: https://github.com/{org}/tasks-{name}", fg="green")
                            ctx.exit(0)
                        except GitHubError as e:
                            click.secho(f"\n✗ Failed to clone repository: {e}", fg="red", err=True)
                            # Ask if they want to create local-only instead
                            if confirm("\nCreate local-only repository instead (without GitHub)?"):
                                github = False
                                click.echo("\nProceeding with local-only repository...")
                            else:
                                click.echo("Cancelled.")
                                ctx.exit(0)
                        except Exception as e:
                            click.secho(f"\n✗ Error initializing repository: {e}", fg="red", err=True)
                            ctx.exit(1)
                    else:
                        # User doesn't want to clone, ask if they want local-only
                        if confirm("\nCreate local-only repository instead (without GitHub)?"):
                            github = False
                            click.echo("\nProceeding with local-only repository...")
                        else:
                            click.echo("Cancelled.")
                            ctx.exit(0)
                except (KeyboardInterrupt, EOFError):
                    click.echo("\nCancelled.")
                    ctx.exit(0)

    else:
        # Non-interactive mode - validate required fields
        if not name:
            click.secho("Error: --name is required in non-interactive mode", fg="red", err=True)
            ctx.exit(1)

        # Handle GitHub integration
        visibility = None
        if github:
            # Use default GitHub org from config if not provided
            if not org:
                org = config.default_github_org
                if not org:
                    click.secho(
                        "Error: --org is required when --github is specified (or set default_github_org in config)",
                        fg="red",
                        err=True,
                    )
                    ctx.exit(1)
            visibility = "private"  # Default to private in non-interactive mode

            # Check if GitHub repo already exists
            if check_github_repo_exists(org, f"tasks-{name}"):
                click.secho(
                    f"Error: Repository tasks-{name} already exists on GitHub at https://github.com/{org}/tasks-{name}",
                    fg="red",
                    err=True,
                )
                click.secho("       Use a different name or clone it manually with: gh repo clone", fg="red", err=True)
                ctx.exit(1)

    try:
        repo = manager.create_repository(name, github_enabled=github, github_org=org, visibility=visibility)
        click.echo()
        click.secho(f"✓ Created repository: {repo.name} at {repo.path}", fg="green")
        if github:
            click.secho(f"✓ GitHub repository created: https://github.com/{org}/tasks-{name}", fg="green")
    except ValueError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        ctx.exit(1)
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        ctx.exit(1)


@cli.command()
@click.pass_context
def repos(ctx):
    """List all task repositories."""
    from taskrepo.core.repository import RepositoryManager

    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    repositories = manager.discover_repositories()

    if not repositories:
        click.echo(f"No repositories found in {config.parent_dir}")
        click.echo("Create one with: taskrepo create-repo <name>")
        return

    click.echo(f"Repositories in {config.parent_dir}:\n")
    for repo in repositories:
        click.echo(f"  • {repo}")


@cli.command()
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    config = ctx.obj["config"]

    click.echo("TaskRepo Configuration:\n")
    click.echo(f"  Config file: {config.config_path}")
    click.echo(f"  Parent directory: {config.parent_dir}")
    click.echo(f"  Default priority: {config.default_priority}")
    click.echo(f"  Default status: {config.default_status}")
    default_assignee = config.default_assignee if config.default_assignee else "(none)"
    click.echo(f"  Default assignee: {default_assignee}")
    default_github_org = config.default_github_org if config.default_github_org else "(none)"
    click.echo(f"  Default GitHub org: {default_github_org}")
    sort_by = ", ".join(config.sort_by)
    click.echo(f"  Sort by: {sort_by}")
    cluster_status = "enabled" if config.cluster_due_dates else "disabled"
    click.echo(f"  Due date clustering: {cluster_status}")


if __name__ == "__main__":
    cli()
