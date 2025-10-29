"""Update checker for TaskRepo CLI.

Checks PyPI for newer versions and notifies users in a non-intrusive way.
Also checks Homebrew for updates when installed via brew.
"""

import json
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from packaging import version

from taskrepo.__version__ import __version__
from taskrepo.utils.homebrew_checker import check_homebrew_update
from taskrepo.utils.install_detector import (
    detect_install_method,
    get_friendly_install_name,
    get_upgrade_command,
)
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
    """Check PyPI and/or Homebrew for newer version of taskrepo.

    For Homebrew installations, checks Homebrew first (more reliable).
    Falls back to PyPI for all other installation methods.

    Returns:
        Latest version string if update available, None otherwise
    """
    try:
        install_method = detect_install_method()

        # For Homebrew installations, check brew first
        if install_method == "homebrew":
            brew_result = check_homebrew_update(__version__)
            if brew_result is not None:
                has_update, latest_version = brew_result
                if has_update:
                    return latest_version
                # No update available via Homebrew
                return None
            # Homebrew check failed, fall through to PyPI

        # Check PyPI for all other methods (or as fallback)
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
    """Display update notification message with installation-specific instructions.

    Args:
        new_version: The latest version available
    """
    import click

    install_method = detect_install_method()
    friendly_name = get_friendly_install_name(install_method)
    upgrade_cmd = get_upgrade_command(install_method)

    click.echo()
    click.echo("─" * 60)
    click.secho(f"⚠️  Update available: v{__version__} → v{new_version}", fg="yellow", bold=True)
    click.echo()

    # Show installation method
    click.echo(f"   Installed via: {friendly_name}")

    # Show upgrade command
    if install_method == "homebrew":
        click.echo("   To upgrade, run: ", nl=False)
        click.secho("tsk upgrade", fg="cyan", bold=True)
        click.echo(f"   (or manually: {upgrade_cmd})")
    else:
        click.echo("   To upgrade, run: ", nl=False)
        click.secho("tsk upgrade", fg="cyan", bold=True)

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
