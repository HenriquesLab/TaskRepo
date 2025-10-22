"""Update checker for TaskRepo CLI.

Checks PyPI for newer versions and notifies users in a non-intrusive way.
"""

import json
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from packaging import version

from taskrepo.__version__ import __version__
from taskrepo.utils.paths import get_update_check_cache_path, migrate_legacy_files

# Check for updates once per day
UPDATE_CHECK_INTERVAL = timedelta(hours=24)
PYPI_JSON_URL = "https://pypi.org/pypi/taskrepo/json"
REQUEST_TIMEOUT = 2  # seconds


def get_cache_file() -> Path:
    """Get the update check cache file path.

    Returns:
        Path to update check cache file
    """
    migrate_legacy_files()
    return get_update_check_cache_path()


def check_for_updates() -> Optional[str]:
    """Check PyPI for newer version of taskrepo.

    Returns:
        Latest version string if update available, None otherwise
    """
    try:
        # Fetch package info from PyPI
        request = urllib.request.Request(PYPI_JSON_URL)
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode())

        latest_version = data["info"]["version"]

        # Compare versions
        if version.parse(latest_version) > version.parse(__version__):
            return latest_version

        return None

    except Exception:
        # Silently fail on any error (network, timeout, parse errors, etc.)
        return None


def should_check_for_updates() -> bool:
    """Check if enough time has passed since last update check.

    Returns:
        True if update check should be performed, False otherwise
    """
    cache_file = get_cache_file()
    if not cache_file.exists():
        return True

    try:
        with open(cache_file) as f:
            cache_data = json.load(f)

        last_check = datetime.fromisoformat(cache_data["last_check"])
        time_since_check = datetime.now() - last_check

        return time_since_check >= UPDATE_CHECK_INTERVAL

    except Exception:
        # If cache is corrupted or unreadable, allow check
        return True


def update_check_cache():
    """Update the cache file with current timestamp."""
    try:
        cache_file = get_cache_file()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {"last_check": datetime.now().isoformat()}
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)
    except Exception:
        # Silently fail if we can't write cache
        pass


def display_update_message(new_version: str):
    """Display update notification message.

    Args:
        new_version: The latest version available
    """
    import click

    click.echo()
    click.echo("─" * 60)
    click.secho(f"⚠️  Update available: v{__version__} → v{new_version}", fg="yellow", bold=True)
    click.echo("─" * 60)


def check_and_notify_updates():
    """Check for updates and display message if available.

    This is the main entry point called from the CLI.
    """
    if not should_check_for_updates():
        return

    # Update cache timestamp
    update_check_cache()

    # Check for updates
    new_version = check_for_updates()
    if new_version:
        display_update_message(new_version)
