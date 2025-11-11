"""Google Calendar synchronization utilities.

This module provides Google Calendar sync functionality for TaskRepo.
Google Calendar support is optional and requires the 'gcal' extras:
    pip install taskrepo[gcal]
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from taskrepo.core.task import Task


class GCalSyncError(Exception):
    """Exception raised for Google Calendar sync errors."""

    pass


def is_gcal_available() -> bool:
    """Check if Google Calendar dependencies are installed.

    Returns:
        True if google-api-python-client and related packages available
    """
    try:
        import google.auth  # noqa: F401
        import google_auth_oauthlib  # noqa: F401
        import googleapiclient.discovery  # noqa: F401

        return True
    except ImportError:
        return False


def get_credentials_file() -> Path:
    """Get path to OAuth credentials file.

    Returns:
        Path to credentials file in ~/.TaskRepo/gcal_credentials.json
    """
    return Path.home() / ".TaskRepo" / "gcal_credentials.json"


def get_token_file() -> Path:
    """Get path to OAuth token file.

    Returns:
        Path to token file in ~/.TaskRepo/gcal_token.json
    """
    return Path.home() / ".TaskRepo" / "gcal_token.json"


def get_mapping_file() -> Path:
    """Get path to task-event mapping file.

    Returns:
        Path to mapping file in ~/.TaskRepo/gcal_mapping.json
    """
    return Path.home() / ".TaskRepo" / "gcal_mapping.json"


def load_task_event_mapping() -> dict[str, str]:
    """Load task UUID to calendar event ID mapping.

    Returns:
        Dictionary mapping task UUIDs to event IDs
    """
    mapping_file = get_mapping_file()
    if not mapping_file.exists():
        return {}

    try:
        with open(mapping_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_task_event_mapping(mapping: dict[str, str]):
    """Save task UUID to calendar event ID mapping.

    Args:
        mapping: Dictionary mapping task UUIDs to event IDs
    """
    mapping_file = get_mapping_file()
    mapping_file.parent.mkdir(parents=True, exist_ok=True)

    with open(mapping_file, "w") as f:
        json.dump(mapping, f, indent=2)


def get_credentials():
    """Get Google Calendar API credentials.

    Returns:
        Credentials object or None if not authenticated

    Raises:
        GCalSyncError: If credentials are invalid or missing
    """
    if not is_gcal_available():
        raise GCalSyncError(
            "Google Calendar dependencies not installed. "
            "Install with: pip install taskrepo[gcal]"
        )

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None
    token_file = get_token_file()

    # Load existing token
    if token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(token_file), ["https://www.googleapis.com/auth/calendar"]
            )
        except Exception:
            pass

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save refreshed credentials
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        except Exception as e:
            raise GCalSyncError(
                f"Failed to refresh credentials: {e}\n"
                "Run 'tsk calendar-setup' to re-authenticate."
            ) from e

    if not creds or not creds.valid:
        raise GCalSyncError(
            "No valid credentials found. "
            "Run 'tsk calendar-setup' to authenticate."
        )

    return creds


def authenticate_google_calendar():
    """Authenticate with Google Calendar using OAuth 2.0.

    Returns:
        Credentials object

    Raises:
        GCalSyncError: If authentication fails
    """
    if not is_gcal_available():
        raise GCalSyncError(
            "Google Calendar dependencies not installed. "
            "Install with: pip install taskrepo[gcal]"
        )

    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials_file = get_credentials_file()
    if not credentials_file.exists():
        raise GCalSyncError(
            "OAuth credentials file not found. "
            "Please set up Google Calendar first."
        )

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_file),
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        creds = flow.run_local_server(port=0)

        # Save credentials
        token_file = get_token_file()
        token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_file, "w") as f:
            f.write(creds.to_json())

        return creds
    except Exception as e:
        raise GCalSyncError(f"Authentication failed: {e}") from e


def task_to_event(task: Task) -> dict:
    """Convert a Task to Google Calendar event format.

    Args:
        task: Task to convert

    Returns:
        Dictionary in Google Calendar event format
    """
    if not task.due:
        raise ValueError("Task must have a due date to sync to calendar")

    # Build event title: [repo] [project] task
    title_parts = []
    if task.repo:
        title_parts.append(f"[{task.repo}]")
    if task.project:
        title_parts.append(f"[{task.project}]")
    title_parts.append(task.title)
    event_title = " ".join(title_parts)

    # Build description with task metadata
    description_parts = []
    if task.description:
        description_parts.append(task.description)
        description_parts.append("")  # Empty line separator
    description_parts.append(f"Task ID: {task.id}")
    description_parts.append(f"Repository: {task.repo}")
    description_parts.append(f"Status: {task.status}")
    description_parts.append(f"Priority: {task.priority}")
    if task.assignees:
        description_parts.append(f"Assignees: {', '.join(task.assignees)}")
    if task.tags:
        description_parts.append(f"Tags: {', '.join(task.tags)}")
    if task.project:
        description_parts.append(f"Project: {task.project}")

    description = "\n".join(description_parts)

    # Determine if all-day event or timed event
    if task.due.hour == 0 and task.due.minute == 0 and task.due.second == 0:
        # All-day event
        event = {
            "summary": event_title,
            "description": description,
            "start": {
                "date": task.due.strftime("%Y-%m-%d"),
            },
            "end": {
                "date": task.due.strftime("%Y-%m-%d"),
            },
        }
    else:
        # Timed event
        # Convert to RFC3339 format with timezone
        due_rfc3339 = task.due.isoformat()
        if task.due.tzinfo is None:
            # Add local timezone if not present
            due_rfc3339 = task.due.replace(tzinfo=timezone.utc).isoformat()

        event = {
            "summary": event_title,
            "description": description,
            "start": {
                "dateTime": due_rfc3339,
            },
            "end": {
                "dateTime": due_rfc3339,
            },
        }

    return event


def sync_tasks_to_gcal(
    tasks: list[Task],
    calendar_id: str = "primary",
    all_tasks_for_cleanup: list[Task] | None = None,
) -> tuple[int, int, int, list[str]]:
    """Sync tasks to Google Calendar.

    Args:
        tasks: List of tasks to sync (with due dates)
        calendar_id: Calendar ID (default: "primary")
        all_tasks_for_cleanup: All tasks (to determine which events to delete)

    Returns:
        Tuple of (created_count, updated_count, deleted_count, errors)

    Raises:
        GCalSyncError: If sync fails
    """
    if not is_gcal_available():
        raise GCalSyncError(
            "Google Calendar dependencies not installed. "
            "Install with: pip install taskrepo[gcal]"
        )

    from googleapiclient.discovery import build

    # Get credentials
    creds = get_credentials()

    try:
        service = build("calendar", "v3", credentials=creds)
    except Exception as e:
        raise GCalSyncError(
            f"Failed to connect to Google Calendar: {e}"
        ) from e

    # Load existing mapping
    mapping = load_task_event_mapping()

    # Track tasks that should exist in calendar
    current_task_ids = {task.id for task in tasks if task.due}

    # Build set of all task IDs that still exist
    # (to distinguish deleted tasks from tasks that became "done")
    if all_tasks_for_cleanup:
        all_existing_task_ids = {task.id for task in all_tasks_for_cleanup}
    else:
        all_existing_task_ids = current_task_ids

    # Sync statistics
    created_count = 0
    updated_count = 0
    deleted_count = 0
    errors = []

    # Create/update events for tasks with due dates
    for task in tasks:
        if not task.due:
            continue

        try:
            event = task_to_event(task)

            if task.id in mapping:
                # Update existing event
                event_id = mapping[task.id]
                try:
                    service.events().update(
                        calendarId=calendar_id,
                        eventId=event_id,
                        body=event,
                    ).execute()
                    updated_count += 1
                except Exception:
                    # If update fails, create new event
                    result = (
                        service.events()
                        .insert(calendarId=calendar_id, body=event)
                        .execute()
                    )
                    mapping[task.id] = result["id"]
                    created_count += 1
            else:
                # Create new event
                result = (
                    service.events()
                    .insert(calendarId=calendar_id, body=event)
                    .execute()
                )
                mapping[task.id] = result["id"]
                created_count += 1

        except Exception as e:
            errors.append(f"Task {task.id[:8]}: {str(e)}")

    # Delete events for tasks that:
    # 1. No longer exist (deleted)
    # 2. No longer should be synced (became "done", lost assignee, etc.)
    # 3. Lost their due date
    tasks_to_delete = [
        task_id
        for task_id in mapping.keys()
        if task_id not in current_task_ids
    ]

    for task_id in tasks_to_delete:
        try:
            event_id = mapping[task_id]
            service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ).execute()
            deleted_count += 1
            del mapping[task_id]
        except Exception as e:
            # If task still exists, show task ID, otherwise show it was deleted
            if task_id in all_existing_task_ids:
                errors.append(f"Delete task {task_id[:8]}: {str(e)}")
            else:
                errors.append(f"Delete deleted task {task_id[:8]}: {str(e)}")

    # Save updated mapping
    save_task_event_mapping(mapping)

    return created_count, updated_count, deleted_count, errors


def test_gcal_connection() -> tuple[bool, Optional[str], list[str]]:
    """Test Google Calendar connection and list calendars.

    Returns:
        Tuple of (success, error_message, calendar_names)
    """
    if not is_gcal_available():
        return (
            False,
            "Google Calendar dependencies not installed. "
            "Install with: pip install taskrepo[gcal]",
            [],
        )

    try:
        from googleapiclient.discovery import build

        creds = get_credentials()
        service = build("calendar", "v3", credentials=creds)

        # List calendars
        calendar_list = service.calendarList().list().execute()

        calendar_names = []
        for calendar in calendar_list.get("items", []):
            name = calendar.get("summary", "Unnamed")
            cal_id = calendar.get("id")
            calendar_names.append(f"{name} ({cal_id})")

        return True, None, calendar_names

    except GCalSyncError as e:
        return False, str(e), []
    except Exception as e:
        return False, str(e), []
