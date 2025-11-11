"""Google Calendar setup command."""

import click
from prompt_toolkit.shortcuts import confirm


@click.command(name="calendar-setup")
@click.pass_context
def calendar_setup(ctx):
    """Set up Google Calendar synchronization.

    Configure TaskRepo to sync tasks with due dates to Google Calendar
    using OAuth 2.0 authentication.

    This feature requires the 'gcal' extras:
        pip install taskrepo[gcal]
    """
    from taskrepo.utils import gcal_sync

    # Check if Google Calendar dependencies are installed
    if not gcal_sync.is_gcal_available():
        click.secho(
            "Google Calendar dependencies not installed!",
            fg="red",
            bold=True,
        )
        click.echo()
        click.echo(
            "To use Google Calendar sync, install TaskRepo with gcal extras:"
        )  # noqa: E501
        click.echo()
        click.secho("  pip install taskrepo[gcal]", fg="cyan", bold=True)
        click.echo()
        click.echo("This will install:")
        click.echo("  • google-api-python-client (Google Calendar API)")
        click.echo("  • google-auth (OAuth 2.0 authentication)")
        click.echo("  • google-auth-oauthlib (OAuth flow)")
        click.echo("  • google-auth-httplib2 (HTTP transport)")
        ctx.exit(1)

    config = ctx.obj["config"]

    click.secho("Google Calendar Setup", fg="cyan", bold=True)
    click.echo()
    click.echo("Configure TaskRepo to sync tasks to Google Calendar.")
    click.echo()

    # Show current configuration if exists
    if config.gcal_enabled:
        click.secho("Current Configuration:", fg="yellow")
        click.echo(f"  Calendar ID: {config.gcal_calendar_id or 'primary'}")
        click.echo(f"  Sync repos: {config.gcal_sync_repos or 'all'}")
        click.echo(f"  Sync statuses: {', '.join(config.gcal_sync_statuses)}")
        click.echo()

        if not confirm("Reconfigure Google Calendar settings?"):
            click.echo("Cancelled.")
            return

        click.echo()

    # Check if credentials file exists
    credentials_file = gcal_sync.get_credentials_file()
    if not credentials_file.exists():
        click.secho(
            "Step 1: Set up OAuth 2.0 Credentials", fg="yellow", bold=True
        )
        click.echo()
        click.echo("You need to create OAuth 2.0 credentials:")
        click.echo()
        click.echo(
            "1. Go to: https://console.cloud.google.com/apis/credentials"
        )  # noqa: E501
        click.echo("2. Create a new project (or select existing)")
        click.echo("3. Enable Google Calendar API:")
        click.echo(
            "   • Go to: https://console.cloud.google.com/apis/library"
        )  # noqa: E501
        click.echo("   • Search for 'Google Calendar API'")
        click.echo("   • Click 'Enable'")
        click.echo("4. Create OAuth 2.0 credentials:")
        click.echo("   • Go back to credentials page")
        click.echo("   • Click 'Create Credentials' → 'OAuth client ID'")
        click.echo("   • Application type: 'Desktop app'")
        click.echo("   • Name: 'TaskRepo' (or any name)")
        click.echo("   • Click 'Create'")
        click.echo("5. Download the credentials:")
        click.echo(
            "   • Click the download button (⬇️) next to your OAuth"
        )  # noqa: E501
        click.echo("   • Save as: ~/.TaskRepo/gcal_credentials.json")
        click.echo()
        click.echo(f"Save credentials to: {credentials_file}")
        click.echo()
        if not confirm("Have you saved the credentials file?"):
            click.echo(
                "Cancelled. Run 'tsk calendar-setup' again when ready."
            )  # noqa: E501
            ctx.exit(0)

        if not credentials_file.exists():
            click.secho(
                f"Error: Credentials file not found: {credentials_file}",
                fg="red",
                err=True,
            )
            ctx.exit(1)

        click.echo()

    # Authenticate with Google
    click.secho("Step 2: Authenticate with Google", fg="yellow", bold=True)
    click.echo()
    click.echo("A browser window will open for authentication.")
    click.echo("Sign in with your Google account and grant permissions.")
    click.echo()
    if not confirm("Ready to authenticate?"):
        click.echo("Cancelled.")
        ctx.exit(0)

    try:
        gcal_sync.authenticate_google_calendar()
        click.echo()
        click.secho("✓ Authentication successful!", fg="green")
    except Exception as e:
        click.secho(f"✗ Authentication failed: {e}", fg="red", err=True)
        ctx.exit(1)

    # Test connection and list calendars
    click.echo()
    click.echo("Testing connection...")

    success, error, calendar_names = gcal_sync.test_gcal_connection()

    if not success:
        click.secho(f"✗ Connection failed: {error}", fg="red", err=True)
        ctx.exit(1)

    click.secho("✓ Connection successful!", fg="green")
    click.echo()

    # Show available calendars
    if calendar_names:
        click.secho(f"Found {len(calendar_names)} calendar(s):", fg="yellow")
        for i, name in enumerate(calendar_names, 1):
            click.echo(f"  {i}. {name}")
        click.echo()

        # Prompt for calendar selection
        if len(calendar_names) > 1:
            from prompt_toolkit import prompt

            calendar_id = prompt(
                "Calendar ID (leave empty for primary): ",
                default="primary",
            ).strip()
        else:
            calendar_id = "primary"
            click.echo("Using primary calendar")
    else:
        calendar_id = "primary"

    # Configure sync options
    click.echo()
    click.secho("Step 3: Sync Options", fg="yellow", bold=True)
    click.echo()

    # Repositories to sync
    from taskrepo.core.repository import RepositoryManager

    manager = RepositoryManager(config.parent_dir)
    repos = manager.discover_repositories()

    if repos:
        click.echo(
            f"Found {len(repos)} repositor{'y' if len(repos) == 1 else 'ies'}:"  # noqa: E501
        )
        for repo in repos:
            click.echo(f"  • {repo.name}")
        click.echo()

        if confirm("Sync all repositories?"):
            sync_repos = None
        else:
            from prompt_toolkit import prompt

            repo_list = prompt(
                "Repository names to sync (comma-separated): "
            ).strip()
            if repo_list:
                sync_repos = [r.strip() for r in repo_list.split(",")]
            else:
                sync_repos = None
    else:
        sync_repos = None

    # Statuses to sync
    click.echo()
    click.echo("Task statuses to sync (default: pending, in-progress):")
    from prompt_toolkit import prompt

    status_input = prompt(
        "Statuses (comma-separated): ",
        default="pending,in-progress",
    ).strip()
    sync_statuses = [s.strip() for s in status_input.split(",")]

    # Save configuration
    config.gcal_calendar_id = calendar_id
    config.gcal_sync_repos = sync_repos
    config.gcal_sync_statuses = sync_statuses
    config.gcal_enabled = True

    click.echo()
    click.secho(
        "✓ Google Calendar configuration saved!", fg="green", bold=True
    )
    click.echo()
    click.echo("Google Calendar sync is now enabled.")
    click.echo()
    click.echo("Next steps:")
    click.echo("  • Run 'tsk sync' to sync tasks to your calendar")
    click.echo("  • Edit ~/.TaskRepo/config to adjust settings")
    click.echo("  • Run 'tsk calendar-setup' again to reconfigure")
