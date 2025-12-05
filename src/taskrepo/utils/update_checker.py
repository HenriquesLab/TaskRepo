"""Update checker for TaskRepo CLI.

Checks PyPI for newer versions and notifies users in a non-intrusive way.
Also checks Homebrew for updates when installed via brew.
"""

import json
import os
import threading
import urllib.request
from datetime import datetime, timedelta
from typing import Optional, Tuple

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


class UpdateChecker:
    """Handles version checking and update notifications."""

    def __init__(self, package_name: str = "taskrepo", current_version: Optional[str] = None):
        """Initialize the update checker.

        Args:
            package_name: Name of the package on PyPI
            current_version: Current version of the package
        """
        self.package_name = package_name
        self.current_version = current_version or __version__
        self.pypi_url = PYPI_JSON_URL
        migrate_legacy_files()
        self.cache_file = get_update_check_cache_path()
        self.check_interval = UPDATE_CHECK_INTERVAL

    def should_check_for_updates(self) -> bool:
        """Determine if we should check for updates.

        Returns:
            bool: True if we should check for updates, False otherwise
        """
        # Check environment variables for opt-out
        if os.getenv("TASKREPO_NO_UPDATE_CHECK", "").lower() in ("1", "true", "yes"):
            return False

        if os.getenv("NO_UPDATE_NOTIFIER", ""):
            return False

        # Check if enough time has passed since last check
        cache_data = self._load_cache()
        if cache_data:
            try:
                last_check = datetime.fromisoformat(cache_data.get("last_check", ""))
                if datetime.now() - last_check < self.check_interval:
                    return False
            except (ValueError, TypeError):
                pass

        return True

    def _load_cache(self) -> Optional[dict]:
        """Load cached update information.

        Returns:
            Dict or None: Cached data if available and valid
        """
        try:
            if self.cache_file.exists():
                with open(self.cache_file, encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def _save_cache(self, data: dict) -> None:
        """Save update information to cache.

        Args:
            data: Data to cache
        """
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass  # Ignore cache write failures

    def _fetch_latest_version(self) -> Optional[str]:
        """Fetch the latest version from PyPI.

        Returns:
            str or None: Latest version if available
        """
        try:
            request = urllib.request.Request(self.pypi_url)
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                data = json.loads(response.read().decode())
                return data["info"]["version"]
        except Exception:
            return None

    def _compare_versions(self, current: str, latest: str) -> bool:
        """Compare two version strings.

        Args:
            current: Current version string
            latest: Latest version string

        Returns:
            bool: True if latest is newer than current
        """
        try:
            return version.parse(latest) > version.parse(current)
        except Exception:
            # Fallback to string comparison
            return latest != current

    def check_for_updates_async(self) -> None:
        """Check for updates in a background thread."""
        if not self.should_check_for_updates():
            return

        def _check():
            self._check_and_cache_update()

        # Run check in background thread to avoid blocking CLI
        thread = threading.Thread(target=_check, daemon=True)
        thread.start()

    def _check_and_cache_update(self) -> None:
        """Check for updates and cache the result."""
        # Try Homebrew first if installed via Homebrew
        install_method = detect_install_method()
        if install_method == "homebrew":
            brew_result = check_homebrew_update(self.current_version)
            if brew_result is not None:
                has_update, latest_version = brew_result
                now = datetime.now()
                cache_data = {
                    "last_check": now.isoformat(),
                    "latest_version": latest_version,
                    "current_version": self.current_version,
                    "update_available": has_update,
                }
                self._save_cache(cache_data)
                return

        # Fall back to PyPI for all other methods
        latest_version = self._fetch_latest_version()
        now = datetime.now()

        cache_data = {
            "last_check": now.isoformat(),
            "latest_version": latest_version,
            "current_version": self.current_version,
            "update_available": False,
        }

        if latest_version:
            cache_data["update_available"] = self._compare_versions(self.current_version, latest_version)

        self._save_cache(cache_data)

    def get_update_notification(self) -> Optional[str]:
        """Get update notification message if an update is available.

        Returns:
            str or None: Notification message if update available
        """
        cache_data = self._load_cache()
        if not cache_data or not cache_data.get("update_available"):
            return None

        # Always use the current runtime version, not cached version
        current = self.current_version
        latest = cache_data.get("latest_version", "unknown")

        if current == "unknown" or latest == "unknown":
            return None

        # Don't show notification if versions are the same
        if current == latest:
            return None

        # Detect installation method and get appropriate upgrade command
        install_method = detect_install_method()
        upgrade_cmd = get_upgrade_command(install_method)
        install_name = get_friendly_install_name(install_method)

        # Format the notification message
        notification_lines = [
            "",
            "─" * 60,
            f"⚠️  Update available: {self.package_name} v{current} → v{latest}",
            "",
            f"   Installed via: {install_name}",
        ]

        # Show upgrade command
        if install_method == "homebrew":
            notification_lines.extend(
                [
                    "   To upgrade, run: tsk upgrade",
                    f"   (or manually: {upgrade_cmd})",
                ]
            )
        else:
            notification_lines.append("   To upgrade, run: tsk upgrade")

        notification_lines.extend(
            [
                "",
                f"   Full details: https://github.com/henriqueslab/taskrepo/releases/tag/v{latest}",
                "─" * 60,
            ]
        )

        return "\n".join(notification_lines)

    def show_update_notification(self) -> None:
        """Show update notification if available."""
        notification = self.get_update_notification()
        if notification:
            import click

            click.echo(notification)

    def force_check(self) -> Tuple[bool, Optional[str]]:
        """Force an immediate update check.

        Returns:
            Tuple[bool, Optional[str]]: (update_available, latest_version)
        """
        install_method = detect_install_method()

        # Try Homebrew first if installed via Homebrew
        if install_method == "homebrew":
            brew_result = check_homebrew_update(self.current_version)
            if brew_result is not None:
                has_update, latest_version = brew_result
                # Update cache
                cache_data = {
                    "last_check": datetime.now().isoformat(),
                    "latest_version": latest_version,
                    "current_version": self.current_version,
                    "update_available": has_update,
                }
                self._save_cache(cache_data)
                return has_update, latest_version

        # Fall back to PyPI
        latest_version = self._fetch_latest_version()

        if not latest_version:
            return False, None

        update_available = self._compare_versions(self.current_version, latest_version)

        # Update cache with forced check
        cache_data = {
            "last_check": datetime.now().isoformat(),
            "latest_version": latest_version,
            "current_version": self.current_version,
            "update_available": update_available,
        }
        self._save_cache(cache_data)

        return update_available, latest_version


# Global instance for easy access (singleton pattern)
_update_checker: Optional[UpdateChecker] = None


def get_update_checker() -> UpdateChecker:
    """Get the global update checker instance."""
    global _update_checker
    if _update_checker is None:
        _update_checker = UpdateChecker()
    return _update_checker


def check_and_notify_updates():
    """Check for updates and display message if available.

    This is the main entry point called from the CLI.
    Runs asynchronously in a background thread.
    """
    checker = get_update_checker()
    checker.check_for_updates_async()


def show_update_notification():
    """Show update notification if available (from cache)."""
    checker = get_update_checker()
    checker.show_update_notification()


def force_update_check() -> Tuple[bool, Optional[str]]:
    """Force an immediate update check.

    Returns:
        Tuple[bool, Optional[str]]: (update_available, latest_version)
    """
    checker = get_update_checker()
    return checker.force_check()
