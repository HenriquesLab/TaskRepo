"""Config command for interactive configuration management."""

from pathlib import Path

import click
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import confirm

from taskrepo.core.config import Config


def _display_config(config):
    """Display current configuration in a formatted way."""
    click.echo()
    click.secho("-" * 50, fg="green")
    click.secho("Current Configuration:", fg="green", bold=True)
    click.secho("-" * 50, fg="green")
    click.echo(f"  Config file: {config.config_path}")
    click.echo(f"  Parent directory: {config.parent_dir}")
    click.echo()
    click.secho("  Task Defaults:", fg="yellow", bold=True)
    click.echo(f"  Default priority: {config.default_priority}")
    click.echo(f"  Default status: {config.default_status}")
    default_assignee = config.default_assignee if config.default_assignee else "(none)"
    click.echo(f"  Default assignee: {default_assignee}")
    default_repo = config.default_repo if config.default_repo else "(none)"
    click.echo(f"  Default repository: {default_repo}")
    click.echo()
    click.secho("  Other Settings:", fg="yellow", bold=True)
    default_github_org = config.default_github_org if config.default_github_org else "(none)"
    click.echo(f"  Default GitHub org: {default_github_org}")
    default_editor = config.default_editor if config.default_editor else "(none - using $EDITOR or vim)"
    click.echo(f"  Default editor: {default_editor}")
    sort_by = ", ".join(config.sort_by)
    click.echo(f"  Sort by: {sort_by}")
    cluster_status = "enabled" if config.cluster_due_dates else "disabled"
    click.echo(f"  Due date clustering: {cluster_status}")
    click.echo(f"  TUI view mode: {config.tui_view_mode}")
    click.secho("-" * 50, fg="green")


@click.command(name="config")
@click.option("--show", is_flag=True, help="Show current configuration (non-interactive)")
@click.pass_context
def config_cmd(ctx, show):
    """Interactive configuration management."""
    config = ctx.obj["config"]

    # If --show flag is provided, display config and exit
    if show:
        _display_config(config)
        return

    while True:
        click.echo()
        click.secho("=" * 50, fg="cyan")
        click.secho("TaskRepo Configuration", fg="cyan", bold=True)
        click.secho("=" * 50, fg="cyan")
        click.echo("\nWhat would you like to configure?\n")
        click.echo("  1. View current settings")
        click.echo("  2. Change parent directory")
        click.echo()
        click.secho("  Task Defaults:", fg="yellow", bold=True)
        click.echo("  3. Set default priority")
        click.echo("  4. Set default status")
        click.echo("  5. Set default assignee")
        click.echo("  6. Set default repository")
        click.echo()
        click.secho("  Other Settings:", fg="yellow", bold=True)
        click.echo("  7. Set default GitHub organization")
        click.echo("  8. Set default editor")
        click.echo("  9. Configure task sorting")
        click.echo(" 10. Toggle due date clustering")
        click.echo(" 11. Set TUI view mode")
        click.echo("\n 12. Reset to defaults")
        click.echo(" 13. Exit")

        try:
            choice = prompt(
                "\nEnter choice (1-13 or Ctrl+C to exit): ",
                completer=WordCompleter(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]),
            )
        except (KeyboardInterrupt, EOFError):
            click.echo()
            click.secho("✓ Configuration saved. Exiting.", fg="green", bold=True)
            break

        choice = choice.strip()

        if choice == "1":
            # View current settings
            _display_config(config)

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
            statuses = ["pending", "in-progress", "completed", "cancelled"]
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
            # Set default repository
            from taskrepo.core.repository import RepositoryManager

            manager = RepositoryManager(config.parent_dir)
            repositories = manager.discover_repositories()

            if not repositories:
                click.secho("✗ No repositories found. Create one first with: tsk create-repo", fg="red")
            else:
                # Sort alphabetically by name
                repositories = manager.sort_repositories_alphabetically(repositories)

                current_repo = config.default_repo if config.default_repo else "(none)"
                click.echo(f"\nCurrent default repository: {current_repo}")
                click.echo("\nAvailable repositories:")
                for idx, repo in enumerate(repositories, start=1):
                    task_count = len(repo.list_tasks())
                    marker = " (current default)" if repo.name == config.default_repo else ""
                    click.echo(f"  {idx}. {repo.name} ({task_count} tasks){marker}")

                try:
                    user_input = prompt(
                        "\nEnter number or repository name (or leave empty to clear default): ",
                        completer=WordCompleter([r.name for r in repositories]),
                    )
                    user_input = user_input.strip()

                    if user_input:
                        # Check if input is a number
                        selected_repo = None
                        try:
                            choice_num = int(user_input)
                            if 1 <= choice_num <= len(repositories):
                                selected_repo = repositories[choice_num - 1].name
                            else:
                                click.secho(f"✗ Invalid number. Please enter 1-{len(repositories)}", fg="red")
                        except ValueError:
                            # Not a number, treat as repository name
                            if manager.get_repository(user_input):
                                selected_repo = user_input
                            else:
                                click.secho(f"✗ Repository '{user_input}' not found", fg="red")

                        if selected_repo:
                            config.default_repo = selected_repo
                            click.secho(f"✓ Default repository updated to: {selected_repo}", fg="green")
                    else:
                        config.default_repo = None
                        click.secho("✓ Default repository cleared", fg="green")
                except (KeyboardInterrupt, EOFError):
                    click.echo("\nCancelled.")

        elif choice == "7":
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

        elif choice == "8":
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

        elif choice == "9":
            # Configure task sorting
            click.echo(f"\nCurrent: {', '.join(config.sort_by)}")

            # Define presets
            example_assignee = config.default_assignee if config.default_assignee else "@me"
            presets = [
                ("due,priority", "By due date, then priority (default)"),
                ("priority,due", "By priority first, then due date"),
                (f"assignee:{example_assignee},due,priority", "My tasks first, then by due date"),
                ("due", "Due date only (simple)"),
                ("-created", "Newest tasks first"),
                ("custom", "Enter custom sort fields (advanced)"),
            ]

            click.echo("\nChoose a preset:")
            for idx, (_sort_value, description) in enumerate(presets, 1):
                click.echo(f"  {idx}. {description}")

            try:
                choice_str = prompt("\nChoice (1-6 or press Enter to cancel): ").strip()
                if not choice_str:
                    click.echo("Cancelled.")
                    continue

                choice_idx = int(choice_str)
                if 1 <= choice_idx <= len(presets):
                    sort_value, description = presets[choice_idx - 1]

                    if sort_value == "custom":
                        # Show advanced options
                        click.echo("\nAvailable fields:")
                        click.echo("  priority, due, created, modified, status, title, project, assignee")
                        click.echo("\nOptions:")
                        click.echo("  • Prefix with '-' for descending (e.g., '-created')")
                        click.echo("  • Use 'assignee:@user' to prioritize specific user")
                        click.echo("\nExamples:")
                        click.echo("  due,priority        - Due date, then priority")
                        click.echo("  assignee:@me,due    - My tasks first")
                        click.echo("  -created            - Newest first")

                        new_sort = prompt("\nEnter custom sort: ").strip()
                        if not new_sort:
                            click.echo("Cancelled.")
                            continue
                        sort_fields = [f.strip() for f in new_sort.split(",") if f.strip()]
                    else:
                        sort_fields = [f.strip() for f in sort_value.split(",")]

                    try:
                        config.sort_by = sort_fields
                        click.secho(f"✓ Sort order: {', '.join(sort_fields)}", fg="green")
                    except ValueError as e:
                        click.secho(f"✗ Error: {e}", fg="red")
                else:
                    click.secho("Invalid choice.", fg="yellow")

            except (ValueError, KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "10":
            # Toggle due date clustering
            is_enabled = config.cluster_due_dates
            status_text = "ON" if is_enabled else "OFF"
            click.secho(f"\nDue date clustering is currently: {status_text}", bold=True)

            click.echo("\nGroups tasks into time buckets (today, this week, etc.) instead of")
            click.echo("exact timestamps. Useful when you want priority to matter within each bucket.")
            click.echo("\nExample: With 'due,priority' sorting")
            click.echo("  OFF: Tasks sorted by exact due date/time")
            click.echo("  ON:  All 'today' tasks grouped, high priority first")

            try:
                # Make the prompt match the action that will be taken
                if is_enabled:
                    should_change = confirm("\nTurn OFF clustering?")
                    if should_change:
                        config.cluster_due_dates = False
                        click.secho("✓ Clustering turned OFF", fg="green")
                    else:
                        click.echo("No changes made.")
                else:
                    should_change = confirm("\nTurn ON clustering?")
                    if should_change:
                        config.cluster_due_dates = True
                        click.secho("✓ Clustering turned ON", fg="green")
                    else:
                        click.echo("No changes made.")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "11":
            # Set TUI view mode
            click.echo(f"\nCurrent TUI view mode: {config.tui_view_mode}")
            click.echo("\nView modes:")
            click.echo("  repo     - Cycle through repositories with left/right arrows")
            click.echo("  project  - Cycle through projects with left/right arrows")
            click.echo("  assignee - Cycle through assignees with left/right arrows")
            try:
                new_mode = prompt(
                    "Enter view mode (repo/project/assignee): ",
                    completer=WordCompleter(["repo", "project", "assignee"], ignore_case=True),
                )
                new_mode = new_mode.strip().lower()
                if new_mode in {"repo", "project", "assignee"}:
                    config.tui_view_mode = new_mode
                    click.secho(f"✓ TUI view mode updated to: {new_mode}", fg="green")
                elif new_mode:
                    click.secho("✗ Invalid view mode. Must be repo, project, or assignee.", fg="red")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "12":
            # Reset to defaults
            click.echo("\n⚠️  This will reset ALL configuration to defaults.")
            try:
                if confirm("Are you sure? This will reset ALL configuration to defaults"):
                    config._data = Config.DEFAULT_CONFIG.copy()
                    config.save()
                    click.secho("✓ Configuration reset to defaults", fg="green")
                else:
                    click.echo("Cancelled.")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "13":
            # Exit
            click.echo()
            click.secho("✓ Configuration saved. Exiting.", fg="green", bold=True)
            break

        else:
            click.secho("✗ Invalid choice. Please enter a number from 1-13.", fg="red")
