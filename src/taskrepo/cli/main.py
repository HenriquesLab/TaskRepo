"""Main CLI entry point for TaskRepo."""

import click

from taskrepo.__version__ import __version__
from taskrepo.cli.commands.add import add
from taskrepo.cli.commands.done import done
from taskrepo.cli.commands.edit import edit
from taskrepo.cli.commands.list import list_tasks
from taskrepo.cli.commands.sync import sync
from taskrepo.core.config import Config


@click.group()
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


# Register commands
cli.add_command(add)
cli.add_command(list_tasks)
cli.add_command(edit)
cli.add_command(done)
cli.add_command(sync)


@cli.command()
@click.pass_context
def init(ctx):
    """Initialize TaskRepo configuration."""
    config = ctx.obj["config"]

    click.echo(f"TaskRepo configuration file: {config.config_path}")
    click.echo(f"Parent directory: {config.parent_dir}")

    if not config.parent_dir.exists():
        if click.confirm(f"Create parent directory {config.parent_dir}?"):
            config.parent_dir.mkdir(parents=True, exist_ok=True)
            click.secho(f"✓ Created {config.parent_dir}", fg="green")
        else:
            click.echo("Skipped directory creation")

    click.secho("✓ TaskRepo initialized", fg="green")


@cli.command()
@click.argument("name")
@click.pass_context
def create_repo(ctx, name):
    """Create a new task repository.

    NAME: Repository name (will be prefixed with 'tasks-')
    """
    from taskrepo.core.repository import RepositoryManager

    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    try:
        repo = manager.create_repository(name)
        click.secho(f"✓ Created repository: {repo.name} at {repo.path}", fg="green")
    except ValueError as e:
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


if __name__ == "__main__":
    cli()
