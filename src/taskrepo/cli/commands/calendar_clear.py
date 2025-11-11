"""Calendar clear command to remove all synced events."""

import click

from taskrepo.core.config import Config


@click.command(name="calendar-clear")
@click.option(
    "--confirm",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.pass_context
def calendar_clear(ctx, confirm):
    """Remove all TaskRepo events from Google Calendar.

    This command will delete all calendar events that were created by TaskRepo
    (tracked in the mapping file) and clear the mapping.

    Use with caution - this cannot be undone!
    """
    from taskrepo.utils import gcal_sync

    config: Config = ctx.obj["config"]

    # Check if Google Calendar is enabled
    if not config.gcal_enabled:
        click.secho(
            "Google Calendar sync is not enabled.",
            fg="yellow",
        )
        click.echo()
        click.echo("To enable it, run: tsk calendar-setup")
        return

    # Check if dependencies are available
    if not gcal_sync.is_gcal_available():
        click.secho(
            "Google Calendar packages are not installed.",
            fg="red",
        )
        click.echo()
        click.echo("Install with: pip install taskrepo[gcal]")
        return

    # Load current mapping to see how many events would be deleted
    mapping = gcal_sync.load_task_event_mapping()

    if not mapping:
        click.secho(
            "✓ No events to delete - calendar is already clear", fg="green"
        )
        return

    # Show what will be deleted
    click.echo()
    click.secho(
        f"Found {len(mapping)} event(s) to delete from Google Calendar",
        fg="yellow",
        bold=True,
    )
    click.echo()

    # Confirm deletion unless --confirm flag was provided
    if not confirm:
        click.echo("This will:")
        click.echo(
            f"  • Delete {len(mapping)} event(s) from calendar: {config.gcal_calendar_id}"
        )
        click.echo("  • Clear the task-event mapping")
        click.echo()
        click.secho("This action cannot be undone!", fg="red", bold=True)
        click.echo()

        if not click.confirm("Are you sure you want to continue?"):
            click.echo()
            click.secho("Cancelled - no events were deleted", fg="yellow")
            return

    # Proceed with deletion
    click.echo()
    click.secho("Deleting events from Google Calendar...", fg="cyan")

    try:
        from googleapiclient.discovery import build

        # Get credentials
        creds = gcal_sync.get_credentials()
        service = build("calendar", "v3", credentials=creds)

        # Delete each event
        deleted_count = 0
        failed_count = 0
        errors = []

        for task_id, event_id in mapping.items():
            try:
                service.events().delete(
                    calendarId=config.gcal_calendar_id,
                    eventId=event_id,
                ).execute()
                deleted_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"Event {event_id[:8]}: {str(e)}")

        # Clear the mapping file
        gcal_sync.save_task_event_mapping({})

        # Show results
        click.echo()
        if deleted_count > 0:
            click.secho(f"✓ Deleted {deleted_count} event(s)", fg="green")

        if failed_count > 0:
            click.secho(
                f"⚠ Failed to delete {failed_count} event(s)", fg="yellow"
            )
            if errors:
                click.echo()
                click.echo("Errors:")
                for error in errors[:10]:  # Show first 10 errors
                    click.echo(f"  • {error}")
                if len(errors) > 10:
                    click.echo(f"  ... and {len(errors) - 10} more")

        if deleted_count == len(mapping) and failed_count == 0:
            click.echo()
            click.secho(
                "✓ All events cleared successfully!", fg="green", bold=True
            )

    except gcal_sync.GCalSyncError as e:
        click.echo()
        click.secho(f"✗ Error: {e}", fg="red")
    except Exception as e:
        click.echo()
        click.secho(f"✗ Unexpected error: {e}", fg="red")
