# Google Calendar Integration Setup Guide

This guide will walk you through setting up Google Calendar synchronization with TaskRepo. With this integration, tasks with deadlines will automatically sync to your Google Calendar as events.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Google Cloud Console Setup](#google-cloud-console-setup)
5. [Running the Setup Wizard](#running-the-setup-wizard)
6. [Configuration Options](#configuration-options)
7. [Usage](#usage)
8. [Troubleshooting](#troubleshooting)
9. [Security & Privacy](#security--privacy)
10. [FAQs](#faqs)

---

## Overview

The Google Calendar integration allows TaskRepo to:
- **Create** calendar events for tasks with deadlines
- **Update** existing events when tasks are modified
- **Delete** events when tasks are removed, marked as "done", or their deadlines are cleared
- **Filter** which tasks to sync based on repository, status, and assignee
- **Handle** both all-day and timed events automatically

### Key Features

- ✅ Free tier usage only (no payment required)
- ✅ OAuth 2.0 authentication (secure, no passwords stored)
- ✅ Automatic token refresh
- ✅ Selective synchronization by repository, status, and assignee
- ✅ Automatic deletion when tasks are completed
- ✅ Bidirectional mapping (task ↔ event)
- ✅ Conflict-free operation (only syncs during `tsk sync`)

---

## Prerequisites

Before starting, ensure you have:

1. **TaskRepo installed** and initialized (`tsk init`)
2. **At least one task repository** set up
3. **A Google account** with access to Google Calendar
4. **Internet connection** for OAuth authentication and syncing

---

## Installation

Install the Google Calendar dependencies using pip with the `gcal` extras:

```bash
pip install taskrepo[gcal]
```

Or if you're using an editable install:

```bash
pip install -e .[gcal]
```

This installs the following packages:
- `google-auth` - Google authentication library
- `google-auth-oauthlib` - OAuth 2.0 flow
- `google-auth-httplib2` - HTTP transport
- `google-api-python-client` - Google Calendar API client

---

## Google Cloud Console Setup

To use the Google Calendar API, you need to create OAuth 2.0 credentials in the Google Cloud Console. Follow these steps carefully:

### Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the **project dropdown** at the top
3. Click **"NEW PROJECT"**
4. Enter a project name (e.g., "TaskRepo Calendar Sync")
5. Click **"CREATE"**

### Step 2: Enable the Google Calendar API

1. In the Cloud Console, select your new project
2. Navigate to **"APIs & Services" > "Library"**
3. Search for **"Google Calendar API"**
4. Click on it and press **"ENABLE"**

### Step 3: Configure the OAuth Consent Screen

1. Go to **"APIs & Services" > "OAuth consent screen"**
2. Select **"External"** user type
3. Click **"CREATE"**
4. Fill in the required fields:
   - **App name**: TaskRepo Calendar Sync
   - **User support email**: Your email
   - **Developer contact information**: Your email
5. Click **"SAVE AND CONTINUE"**
6. On the **Scopes** page, click **"ADD OR REMOVE SCOPES"**
7. Search for and select:
   - `https://www.googleapis.com/auth/calendar` (or just select "Google Calendar API")
8. Click **"UPDATE"** then **"SAVE AND CONTINUE"**
9. On the **Test users** page (if in testing mode):
   - Click **"ADD USERS"**
   - Add your Google email address
   - Click **"SAVE AND CONTINUE"**
10. Review and click **"BACK TO DASHBOARD"**

### Step 4: Create OAuth 2.0 Credentials

1. Go to **"APIs & Services" > "Credentials"**
2. Click **"CREATE CREDENTIALS"** at the top
3. Select **"OAuth client ID"**
4. For **Application type**, select **"Desktop app"**
5. Enter a name (e.g., "TaskRepo Desktop Client")
6. Click **"CREATE"**
7. A dialog will appear with your credentials. Click **"DOWNLOAD JSON"**
8. Save the downloaded JSON file as `gcal_credentials.json` in your TaskRepo config directory:
   - **Default location**: `~/.TaskRepo/gcal_credentials.json`

**Important**: Keep this file secure! It contains sensitive credentials.

### Step 5: (Optional) Publish Your App

If you want to use this integration long-term without the "This app isn't verified" warning:

1. Go to **"OAuth consent screen"**
2. Click **"PUBLISH APP"**
3. Confirm the publishing

Note: For personal use, publishing is not required. You can click "Advanced" → "Go to TaskRepo (unsafe)" during authentication.

---

## Running the Setup Wizard

Once you have the OAuth credentials file in place, run the interactive setup wizard:

```bash
tsk calendar-setup
```

The wizard will guide you through:

### 1. Dependency Check

The wizard verifies that all required Google Calendar packages are installed.

```
Checking for Google Calendar dependencies...
✓ All required packages are installed
```

If packages are missing, install them with: `pip install taskrepo[gcal]`

### 2. Credentials File Check

The wizard checks for `~/.TaskRepo/gcal_credentials.json`.

```
Checking for credentials file...
✓ Found credentials file at: /Users/yourname/.TaskRepo/gcal_credentials.json
```

If the file is missing, the wizard will show detailed instructions for creating it.

### 3. OAuth Authentication

The wizard will open your default web browser for authentication:

```
Starting OAuth authentication...

A browser window will open for Google authentication.
Please sign in and authorize the application.

If the browser doesn't open automatically, visit this URL:
https://accounts.google.com/o/oauth2/auth?...
```

**What to do:**
1. A browser window opens automatically
2. Sign in with your Google account
3. Review the permissions requested
4. Click **"Allow"**
5. You'll see "The authentication flow has completed. You may close this window."
6. Return to the terminal

After successful authentication:
```
✓ Successfully authenticated with Google Calendar!
```

The access and refresh tokens are saved to `~/.TaskRepo/gcal_token.json`.

### 4. Connection Test

The wizard tests the connection and lists available calendars:

```
Testing connection to Google Calendar...

✓ Successfully connected to Google Calendar!

Available calendars:
  1. Primary (your.email@gmail.com)
  2. Work Calendar
  3. Personal Projects
```

### 5. Calendar Selection

Choose which calendar to sync tasks to:

```
Select calendar to use [1-3, or press Enter for Primary]:
```

Enter the number or press Enter to use your primary calendar.

### 6. Repository Filter

Choose whether to sync tasks from all repositories or only specific ones:

```
Do you want to sync tasks from all repositories? [Y/n]:
```

- **Y** (default): Syncs tasks from all repositories
- **n**: Prompts you to select specific repositories

If you choose specific repositories:
```
Available repositories:
  1. work-tasks
  2. personal
  3. project-alpha

Select repositories to sync (comma-separated, e.g., 1,3): 1,2
```

### 7. Status Filter

Choose which task statuses to sync:

```
Current sync statuses: pending, in-progress

Available statuses:
  • pending
  • in-progress
  • done
  • cancelled

Enter statuses to sync (comma-separated) [pending,in-progress]:
```

Press Enter to keep the default (pending, in-progress) or specify different statuses.

**Note**: Tasks with "done" or "cancelled" status typically shouldn't be synced as active calendar events.

### 8. Completion

```
✓ Google Calendar sync has been configured!

Configuration saved:
  • Enabled: Yes
  • Calendar: Primary
  • Repositories: All
  • Statuses: pending, in-progress

Tasks will now sync to Google Calendar automatically during 'tsk sync'.
```

---

## Configuration Options

The Google Calendar configuration is stored in `~/.TaskRepo/config` and can be viewed/modified with:

```bash
tsk config-show
```

### Available Settings

| Setting | Description | Default | Example Values |
|---------|-------------|---------|----------------|
| `gcal_enabled` | Enable/disable Google Calendar sync | `false` | `true`, `false` |
| `gcal_calendar_id` | Calendar to sync to | `"primary"` | `"primary"`, `"calendar-id@group.calendar.google.com"` |
| `gcal_sync_repos` | Repositories to sync (null = all) | `null` | `["work-tasks", "personal"]` |
| `gcal_sync_statuses` | Task statuses to sync | `["pending", "in-progress"]` | `["pending", "done"]` |

### Manual Configuration

You can manually edit the configuration using:

```bash
tsk config gcal_enabled true
tsk config gcal_calendar_id "primary"
tsk config gcal_sync_repos '["work-tasks"]'
tsk config gcal_sync_statuses '["pending","in-progress"]'
```

---

## Usage

Once configured, Google Calendar sync happens automatically during the `tsk sync` command.

### Automatic Sync with Git

```bash
tsk sync
```

This will:
1. Perform git sync operations (push/pull)
2. Sync tasks to Google Calendar (if `gcal_enabled` is true)

Example output:
```
Starting sync operations...

Syncing repository: work-tasks
✓ Pulled latest changes from origin/main
✓ Pushed local changes to origin/main

Syncing tasks to Google Calendar...
✓ Created 3 event(s)
✓ Updated 1 event(s)
✓ Deleted 0 event(s)

✓ Sync completed successfully!
```

### Clearing All Calendar Events

If you want to remove all TaskRepo events from your Google Calendar:

```bash
tsk calendar-clear
```

This command will:
- Show how many events will be deleted
- Ask for confirmation (unless you use `--confirm` flag)
- Delete all events that were created by TaskRepo
- Clear the task-event mapping

**Warning**: This action cannot be undone! Use with caution.

Example:
```bash
# Interactive with confirmation
tsk calendar-clear

# Skip confirmation prompt
tsk calendar-clear --confirm
```

### What Gets Synced

TaskRepo syncs tasks to Google Calendar based on these rules:

1. **Must have a due date**: Only tasks with `due:` field are synced
2. **Must match repository filter**: If `gcal_sync_repos` is set, only tasks from those repos
3. **Must match status filter**: Only tasks with statuses in `gcal_sync_statuses`
4. **Must match assignee filter**: If `default_assignee` is set, only tasks assigned to that user (or unassigned tasks)
5. **Creates calendar events**:
   - **All-day events**: If only date is specified (e.g., `due: 2024-03-15`)
   - **Timed events**: If time is specified (e.g., `due: 2024-03-15 14:30`)

### Event Lifecycle

- **Creation**: When a task with a due date matches all filters
- **Update**: When task details change (title, description, due date, etc.)
- **Deletion**: When:
  - Task is deleted
  - Task status changes to "done" or "cancelled" (if not in `gcal_sync_statuses`)
  - Task loses its due date
  - Task assignee changes and no longer matches `default_assignee`
  - Task repository no longer matches `gcal_sync_repos`

### Event Properties

| Task Field | Calendar Event Field |
|------------|---------------------|
| Repository name + Project name + Task title | Event title (e.g., "[work-tasks] [project-alpha] Fix bug") |
| Due date/time | Event start time |
| Due date/time + 1 hour | Event end time (for timed events) |
| Task description | Event description |

**Event Title Format:**
- With repository and project: `[repo-name] [project-name] Task Title`
- With repository only: `[repo-name] Task Title`
- Task title only if no repository: `Task Title`

This format makes it easy to identify which repository and project each task belongs to directly in your calendar view.

### Task-to-Event Mapping

TaskRepo maintains a mapping file at `~/.TaskRepo/gcal_mapping.json` that tracks:
- Which task UUID corresponds to which calendar event ID
- The last modification time of each task

This ensures:
- Updates modify the correct event
- Deletions remove the correct event
- No duplicate events are created

---

## Troubleshooting

### "Google Calendar packages not installed"

**Problem**: Dependencies are missing.

**Solution**:
```bash
pip install taskrepo[gcal]
```

### "Credentials file not found"

**Problem**: `~/.TaskRepo/gcal_credentials.json` doesn't exist.

**Solution**: Follow the [Google Cloud Console Setup](#google-cloud-console-setup) steps to create and download OAuth credentials.

### "Failed to authenticate"

**Problem**: OAuth flow failed or was cancelled.

**Solution**:
1. Make sure you completed the browser authentication
2. Check that you allowed all requested permissions
3. Try running `tsk calendar-setup` again
4. If issues persist, delete `~/.TaskRepo/gcal_token.json` and re-authenticate

### "Access token expired" or "Invalid credentials"

**Problem**: The OAuth token has expired or is invalid.

**Solution**: TaskRepo automatically refreshes tokens, but if you see this error:
1. Delete `~/.TaskRepo/gcal_token.json`
2. Run `tsk calendar-setup` again to re-authenticate

### "This app isn't verified" warning during OAuth

**Problem**: Google shows a warning because your app is in testing mode.

**Solution**:
1. Click **"Advanced"**
2. Click **"Go to TaskRepo (unsafe)"**
3. This is safe for your own personal app
4. Alternatively, publish your app in Google Cloud Console (see Step 5 in setup)

### Events not syncing

**Problem**: Running `tsk sync` but events aren't appearing in calendar.

**Solution**:
1. Check that `gcal_enabled` is `true`: `tsk config-show`
2. Verify tasks have due dates: `tsk list`
3. Check repository filter: ensure tasks are in synced repos
4. Check status filter: ensure tasks have synced statuses
5. Test connection: `tsk calendar-setup` → follow test connection step
6. Check for errors in sync output

### Duplicate events

**Problem**: Same task appears multiple times in calendar.

**Solution**:
1. This shouldn't happen due to mapping file
2. Delete duplicate events manually in Google Calendar
3. Delete `~/.TaskRepo/gcal_mapping.json`
4. Run `tsk sync` again to recreate clean mappings

### Rate limiting

**Problem**: "Quota exceeded" or "Rate limit" errors.

**Solution**:
- Google Calendar API has generous free tier limits
- If you hit limits, wait a few minutes and try again
- Reduce sync frequency if needed

---

## Security & Privacy

### What Data is Stored Locally?

TaskRepo stores these files in `~/.TaskRepo/`:

1. **`gcal_credentials.json`**:
   - OAuth client ID and client secret
   - Used to initiate authentication flow
   - **Do not share this file**

2. **`gcal_token.json`**:
   - Access token (expires after ~1 hour)
   - Refresh token (used to get new access tokens)
   - **Do not share this file**

3. **`gcal_mapping.json`**:
   - Task UUID to calendar event ID mapping
   - Last modification timestamps
   - Contains no sensitive data

### What Permissions are Requested?

TaskRepo requests:
- **Google Calendar API scope**: Full read/write access to your calendars
- This is required to create, update, and delete events

### Can I Revoke Access?

Yes! You can revoke TaskRepo's access anytime:

1. Go to [Google Account Permissions](https://myaccount.google.com/permissions)
2. Find "TaskRepo Calendar Sync" (or your app name)
3. Click **"Remove access"**

After revoking, delete the token file:
```bash
rm ~/.TaskRepo/gcal_token.json
```

### Is OAuth 2.0 Secure?

Yes! OAuth 2.0 is industry-standard:
- No passwords are stored locally
- Tokens are encrypted in transit
- Refresh tokens allow re-authentication without browser flow
- You can revoke access anytime from Google Account settings

---

## FAQs

### Q: Do I need to pay for Google Calendar API?

**A**: No! Google Calendar API has a generous free tier that's more than sufficient for personal task management. There's no payment or subscription required.

### Q: Can I sync to multiple calendars?

**A**: Currently, TaskRepo syncs to one calendar at a time (configured in `gcal_calendar_id`). You can change which calendar anytime by running `tsk calendar-setup` again.

### Q: What happens if I mark a task as "done"?

**A**: The next time you run `tsk sync`, the corresponding calendar event will be automatically deleted from Google Calendar (assuming "done" is not in your `gcal_sync_statuses`, which is the default).

### Q: Can I sync only tasks assigned to me?

**A**: Yes! Set your `default_assignee` in the config, and only tasks assigned to you (or unassigned tasks) will be synced:
```bash
tsk config default_assignee "@yourusername"
```

Then run:
```bash
tsk sync
```

Tasks not assigned to you will be filtered out. If a task's assignee changes, its calendar event will be deleted on the next sync.

### Q: What happens if I change a task in TaskRepo?

**A**: The next time you run `tsk sync`, the corresponding calendar event will be updated automatically.

### Q: What happens if I delete a task?

**A**: The next time you run `tsk sync`, the corresponding calendar event will be deleted from Google Calendar.

### Q: Can I edit events in Google Calendar?

**A**: You can, but changes won't sync back to TaskRepo. This is one-way sync (TaskRepo → Google Calendar). If you run `tsk sync` again, TaskRepo will overwrite the calendar event with its version.

### Q: Does sync happen automatically?

**A**: Sync happens during `tsk sync`, which you typically run after making changes to your tasks. This gives you control over when syncing occurs.

### Q: Can I disable sync temporarily?

**A**: Yes! Set `gcal_enabled` to `false`:
```bash
tsk config gcal_enabled false
```

To re-enable:
```bash
tsk config gcal_enabled true
```

### Q: What if I have tasks without due dates?

**A**: Tasks without due dates are not synced to calendar (since there's no meaningful date/time for the event).

### Q: Can I sync completed tasks?

**A**: You can by adding "done" to `gcal_sync_statuses`, but it's not recommended. Completed tasks typically shouldn't appear as active calendar events.

### Q: How often do tokens expire?

**A**: Access tokens expire after ~1 hour, but TaskRepo automatically refreshes them using the refresh token. You shouldn't need to re-authenticate frequently.

### Q: Can multiple people sync to the same calendar?

**A**: Technically yes, but each person needs their own OAuth credentials and would need to authenticate separately. This isn't a recommended use case.

### Q: What happens during conflicts?

**A**: TaskRepo sync is one-directional (TaskRepo → Google Calendar), so there are no conflicts. TaskRepo is the source of truth.

---

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [TaskRepo GitHub Issues](https://github.com/yourusername/TaskRepo/issues)
2. Create a new issue with:
   - Error message
   - Steps to reproduce
   - Your configuration (sanitized, no credentials)
3. Check Google Calendar API [Status Dashboard](https://www.google.com/appsstatus)

---

## Next Steps

Now that Google Calendar sync is set up:

1. Add some tasks with due dates:
   ```bash
   tsk add "Finish project report" --due "2024-03-15 14:00"
   tsk add "Team meeting" --due "2024-03-16 10:30"
   ```

2. Sync to calendar:
   ```bash
   tsk sync
   ```

3. Check your Google Calendar to see the events!

4. Modify a task and sync again to see updates:
   ```bash
   tsk edit <task-id> --due "2024-03-15 15:00"
   tsk sync
   ```

Happy syncing! 🗓️✨
