"""Config command for interactive configuration management."""

from pathlib import Path

import click
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import confirm

from taskrepo.core.config import Config


@click.command(name="config")
@click.pass_context
def config_cmd(ctx):
    """Interactive configuration management."""
    config = ctx.obj["config"]

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
        click.echo("\n 11. Reset to defaults")
        click.echo(" 12. Exit")

        try:
            choice = prompt(
                "\nEnter choice (1-12): ",
                completer=WordCompleter(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]),
            )
        except (KeyboardInterrupt, EOFError):
            click.echo("\nExiting configuration.")
            break

        choice = choice.strip()

        if choice == "1":
            # View current settings
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
            click.secho("-" * 50, fg="green")

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
            # Set default repository
            from taskrepo.core.repository import RepositoryManager

            manager = RepositoryManager(config.parent_dir)
            repositories = manager.discover_repositories()

            if not repositories:
                click.secho("✗ No repositories found. Create one first with: tsk create-repo", fg="red")
            else:
                current_repo = config.default_repo if config.default_repo else "(none)"
                click.echo(f"\nCurrent default repository: {current_repo}")
                click.echo("\nAvailable repositories:")
                for idx, repo in enumerate(repositories, start=1):
                    marker = " (current default)" if repo.name == config.default_repo else ""
                    click.echo(f"  {idx}. {repo.name}{marker}")

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
            click.echo(f"\nCurrent sort order: {', '.join(config.sort_by)}")
            cluster_status = "enabled" if config.cluster_due_dates else "disabled"
            click.echo(f"Due date clustering: {cluster_status}")
            click.echo("\nAvailable sort fields:")
            click.echo("  priority, due, created, modified, status, title, project, assignee")
            click.echo("\nSpecial assignee syntax:")
            click.echo("  assignee                - Sort by first assignee alphabetically")
            click.echo("  assignee:@username      - Tasks for @username appear first")
            click.echo("  -assignee:@username     - Tasks NOT for @username appear first")
            click.echo("\nGeneral options:")
            click.echo("  Prefix with '-' for descending order (e.g., '-created', '-priority')")

            # Use default assignee in examples if set, otherwise use generic placeholder
            example_assignee = config.default_assignee if config.default_assignee else "@username"
            click.echo("\nExamples:")
            click.echo(f"  assignee:{example_assignee},due,priority    - Your tasks first, then by due date")
            click.echo("  due,priority,-created              - Due date, priority, newest first")

            click.echo("\n" + "─" * 60)
            click.secho("About Due Date Clustering", fg="cyan", bold=True)
            click.echo("─" * 60)
            if config.cluster_due_dates:
                click.secho("Currently: ENABLED", fg="green")
            else:
                click.secho("Currently: DISABLED", fg="yellow")
            click.echo("\nWhen enabled, tasks are grouped by countdown time buckets:")
            click.echo("  • Overdue (2+ weeks, 1 week, 1-6 days)")
            click.echo("  • Today, Tomorrow, 2-3 days, 4-13 days")
            click.echo("  • 1-3 weeks, 1 month, 2+ months")
            click.echo("\nWithout clustering (default):")
            click.echo("  Tasks sorted by exact due date timestamps")
            click.echo("  Example: Task A (due 11:59 PM) before Task B (due 12:01 AM next day)")
            click.echo("\nWith clustering:")
            click.echo("  Tasks in same bucket sorted by next field (e.g., priority)")
            click.echo("  Example: All 'today' tasks grouped, high priority before low")
            click.echo("\nUseful when: You have many tasks with similar due dates and want")
            click.echo("             secondary fields (like priority) to matter within each bucket")
            click.echo("\nToggle clustering: Choose option 10 from main menu")
            click.echo("─" * 60)
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

        elif choice == "10":
            # Toggle due date clustering
            current_status = "enabled" if config.cluster_due_dates else "disabled"
            click.echo(f"\nDue date clustering is currently: {current_status}")
            click.echo("\nWhen enabled, tasks are grouped by countdown buckets (today, this week, this month)")
            click.echo("instead of exact due dates. This allows secondary sort fields (like priority)")
            click.echo("to take precedence within each time bucket.")
            click.echo("\nExample with clustering enabled and sort_by=['due', 'priority']:")
            click.echo("  Today:")
            click.echo("    - High priority task")
            click.echo("    - Medium priority task")
            click.echo("  This week:")
            click.echo("    - High priority task")
            click.echo("    - Low priority task")
            try:
                new_value = confirm("\nEnable due date clustering?")
                config.cluster_due_dates = new_value
                new_status = "enabled" if new_value else "disabled"
                click.secho(f"✓ Due date clustering {new_status}", fg="green")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nCancelled.")

        elif choice == "11":
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

        elif choice == "12":
            # Exit
            click.echo("\nExiting configuration.")
            break

        else:
            click.secho("✗ Invalid choice. Please enter a number from 1-12.", fg="red")
