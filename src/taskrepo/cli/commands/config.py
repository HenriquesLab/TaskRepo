"""Config command for interactive configuration management."""

from pathlib import Path

import click
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

from taskrepo.core.config import Config


@click.command(name="config")
@click.pass_context
def config_cmd(ctx):
    """Interactive configuration management."""
    config = ctx.obj["config"]

    while True:
        click.echo("\n" + "=" * 50)
        click.echo("TaskRepo Configuration")
        click.echo("=" * 50)
        click.echo("\nWhat would you like to configure?\n")
        click.echo("  1. View current settings")
        click.echo("  2. Change parent directory")
        click.echo("  3. Set default priority")
        click.echo("  4. Set default status")
        click.echo("  5. Set default assignee")
        click.echo("  6. Configure task sorting")
        click.echo("  7. Set default editor")
        click.echo("  8. Set default GitHub organization")
        click.echo("  9. Reset to defaults")
        click.echo(" 10. Exit")

        try:
            choice = prompt(
                "\nEnter choice (1-10): ",
                completer=WordCompleter(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]),
            )
        except (KeyboardInterrupt, EOFError):
            click.echo("\nExiting configuration.")
            break

        choice = choice.strip()

        if choice == "1":
            # View current settings
            click.echo("\n" + "-" * 50)
            click.echo("Current Configuration:")
            click.echo("-" * 50)
            click.echo(f"  Config file: {config.config_path}")
            click.echo(f"  Parent directory: {config.parent_dir}")
            click.echo(f"  Default priority: {config.default_priority}")
            click.echo(f"  Default status: {config.default_status}")
            default_assignee = config.default_assignee if config.default_assignee else "(none)"
            click.echo(f"  Default assignee: {default_assignee}")
            default_github_org = config.default_github_org if config.default_github_org else "(none)"
            click.echo(f"  Default GitHub org: {default_github_org}")
            default_editor = config.default_editor if config.default_editor else "(none - using $EDITOR or vim)"
            click.echo(f"  Default editor: {default_editor}")
            sort_by = ", ".join(config.sort_by)
            click.echo(f"  Sort by: {sort_by}")
            click.echo("-" * 50)

        elif choice == "2":
            # Change parent directory
            click.echo(f"\nCurrent parent directory: {config.parent_dir}")
            try:
                new_dir = prompt("Enter new parent directory (or press Enter to cancel): ")
                if new_dir.strip():
                    config.parent_dir = Path(new_dir.strip()).expanduser()
                    click.secho(f"✓ Parent directory updated to: {config.parent_dir}", fg="green")
                else:
                    click.echo("Cancelled.")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "3":
            # Set default priority
            click.echo(f"\nCurrent default priority: {config.default_priority}")
            try:
                new_priority = prompt(
                    "Enter default priority (H/M/L): ",
                    completer=WordCompleter(["H", "M", "L"], ignore_case=True),
                )
                new_priority = new_priority.strip().upper()
                if new_priority in {"H", "M", "L"}:
                    config.default_priority = new_priority
                    click.secho(f"✓ Default priority updated to: {new_priority}", fg="green")
                elif new_priority:
                    click.secho("✗ Invalid priority. Must be H, M, or L.", fg="red")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "4":
            # Set default status
            click.echo(f"\nCurrent default status: {config.default_status}")
            statuses = ["pending", "in_progress", "completed", "cancelled"]
            try:
                new_status = prompt(
                    "Enter default status: ",
                    completer=WordCompleter(statuses, ignore_case=True),
                )
                new_status = new_status.strip().lower()
                if new_status in statuses:
                    config.default_status = new_status
                    click.secho(f"✓ Default status updated to: {new_status}", fg="green")
                elif new_status:
                    click.secho(f"✗ Invalid status. Must be one of: {', '.join(statuses)}", fg="red")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "5":
            # Set default assignee
            current_assignee = config.default_assignee if config.default_assignee else "(none)"
            click.echo(f"\nCurrent default assignee: {current_assignee}")
            try:
                new_assignee = prompt("Enter default assignee (GitHub handle, or leave empty for none): ")
                new_assignee = new_assignee.strip()
                if new_assignee:
                    if not new_assignee.startswith("@"):
                        new_assignee = f"@{new_assignee}"
                    config.default_assignee = new_assignee
                    click.secho(f"✓ Default assignee updated to: {new_assignee}", fg="green")
                else:
                    config.default_assignee = None
                    click.secho("✓ Default assignee cleared", fg="green")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "6":
            # Configure task sorting
            click.echo(f"\nCurrent sort order: {', '.join(config.sort_by)}")
            click.echo("\nAvailable sort fields:")
            click.echo("  priority, due, created, modified, status, title, project")
            click.echo("  (prefix with '-' for descending order, e.g., '-created')")
            try:
                new_sort = prompt("Enter sort fields (comma-separated): ")
                if new_sort.strip():
                    sort_fields = [f.strip() for f in new_sort.split(",") if f.strip()]
                    try:
                        config.sort_by = sort_fields
                        click.secho(f"✓ Sort order updated to: {', '.join(sort_fields)}", fg="green")
                    except ValueError as e:
                        click.secho(f"✗ Error: {e}", fg="red")
                else:
                    click.echo("Cancelled.")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "7":
            # Set default editor
            current_editor = config.default_editor if config.default_editor else "(none - using $EDITOR or vim)"
            click.echo(f"\nCurrent default editor: {current_editor}")
            click.echo("\nCommon editors: vim, nano, emacs, code, subl, gedit")
            try:
                new_editor = prompt("Enter default editor command (or leave empty for none): ")
                new_editor = new_editor.strip()
                if new_editor:
                    config.default_editor = new_editor
                    click.secho(f"✓ Default editor updated to: {new_editor}", fg="green")
                else:
                    config.default_editor = None
                    click.secho("✓ Default editor cleared (will use $EDITOR or vim)", fg="green")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "8":
            # Set default GitHub organization
            current_org = config.default_github_org if config.default_github_org else "(none)"
            click.echo(f"\nCurrent default GitHub organization: {current_org}")
            try:
                new_org = prompt("Enter default GitHub organization/owner (or leave empty for none): ")
                new_org = new_org.strip()
                if new_org:
                    config.default_github_org = new_org
                    click.secho(f"✓ Default GitHub organization updated to: {new_org}", fg="green")
                else:
                    config.default_github_org = None
                    click.secho("✓ Default GitHub organization cleared", fg="green")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "9":
            # Reset to defaults
            click.echo("\n⚠️  This will reset ALL configuration to defaults.")
            try:
                confirm = prompt("Are you sure? (yes/no): ")
                if confirm.strip().lower() in {"yes", "y"}:
                    config._data = Config.DEFAULT_CONFIG.copy()
                    config.save()
                    click.secho("✓ Configuration reset to defaults", fg="green")
                else:
                    click.echo("Cancelled.")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "10":
            # Exit
            click.echo("\nExiting configuration.")
            break

        else:
            click.secho("✗ Invalid choice. Please enter a number from 1-10.", fg="red")
