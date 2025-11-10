"""Sync history tracking for reliable status monitoring.

This module provides persistent logging of sync attempts to avoid false positive
errors from competing sync mechanisms with flag resets.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class SyncHistoryEntry:
    """Record of a single sync attempt.

    Attributes:
        timestamp: Unix timestamp when sync occurred
        success: Whether the sync fully succeeded
        repos_synced: List of repository names that synced successfully
        repos_failed: List of repository names that failed to sync
        error_message: Optional error description if sync failed
    """

    timestamp: float
    success: bool
    repos_synced: list[str]
    repos_failed: list[str]
    error_message: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "SyncHistoryEntry":
        """Create entry from dictionary."""
        return SyncHistoryEntry(
            timestamp=data["timestamp"],
            success=data["success"],
            repos_synced=data.get("repos_synced", []),
            repos_failed=data.get("repos_failed", []),
            error_message=data.get("error_message"),
        )


class SyncHistory:
    """Manages persistent log of sync attempts.

    Stores the last 10 sync attempts in ~/.TaskRepo/sync_history.json
    to provide reliable status tracking across TUI sessions.
    """

    def __init__(self, max_entries: int = 10):
        """Initialize sync history.

        Args:
            max_entries: Maximum number of entries to keep (default: 10)
        """
        self.max_entries = max_entries
        self.entries: list[SyncHistoryEntry] = []
        self.history_file = Path.home() / ".TaskRepo" / "sync_history.json"

        # Load existing history if available
        self.load()

    def add_entry(
        self,
        success: bool,
        repos_synced: list[str] | None = None,
        repos_failed: list[str] | None = None,
        error_message: str | None = None,
    ) -> None:
        """Add a new sync entry to the history.

        Automatically saves to disk and maintains max_entries limit.

        Args:
            success: Whether the sync fully succeeded
            repos_synced: List of successfully synced repository names
            repos_failed: List of failed repository names
            error_message: Optional error description
        """
        import time

        entry = SyncHistoryEntry(
            timestamp=time.time(),
            success=success,
            repos_synced=repos_synced or [],
            repos_failed=repos_failed or [],
            error_message=error_message,
        )

        # Add to front of list (most recent first)
        self.entries.insert(0, entry)

        # Trim to max_entries
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[: self.max_entries]

        # Save to disk
        self.save()

    def get_last_sync(self) -> SyncHistoryEntry | None:
        """Get the most recent sync entry (success or failure).

        Returns:
            Most recent sync entry, or None if no history
        """
        return self.entries[0] if self.entries else None

    def get_last_successful_sync(self) -> SyncHistoryEntry | None:
        """Get the most recent successful sync entry.

        Returns:
            Most recent successful sync, or None if none found
        """
        for entry in self.entries:
            if entry.success:
                return entry
        return None

    def has_recent_errors(self, count: int = 3) -> bool:
        """Check if the last N syncs have errors.

        Args:
            count: Number of recent syncs to check (default: 3)

        Returns:
            True if any of the last N syncs failed
        """
        recent = self.entries[:count]
        return any(not entry.success for entry in recent)

    def get_error_count(self, count: int = 10) -> int:
        """Count how many of the last N syncs failed.

        Args:
            count: Number of recent syncs to check (default: 10)

        Returns:
            Number of failed syncs
        """
        recent = self.entries[:count]
        return sum(1 for entry in recent if not entry.success)

    def save(self) -> None:
        """Save history to disk (~/.TaskRepo/sync_history.json)."""
        # Ensure directory exists
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert entries to dict format
        data = {"entries": [entry.to_dict() for entry in self.entries]}

        # Write to file
        with open(self.history_file, "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        """Load history from disk if available."""
        if not self.history_file.exists():
            self.entries = []
            return

        try:
            with open(self.history_file) as f:
                data = json.load(f)

            # Convert dict entries to SyncHistoryEntry objects
            self.entries = [SyncHistoryEntry.from_dict(entry) for entry in data.get("entries", [])]

            # Ensure we don't exceed max_entries
            if len(self.entries) > self.max_entries:
                self.entries = self.entries[: self.max_entries]

        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupted file - start fresh
            self.entries = []

    def clear(self) -> None:
        """Clear all history and delete the file."""
        self.entries = []
        if self.history_file.exists():
            self.history_file.unlink()

    def format_last_sync(self) -> str:
        """Format the last sync entry as a human-readable string.

        Returns:
            Formatted string like "Synced 2m ago (3/5 repos)" or "Sync failed 5m ago"
        """
        last = self.get_last_sync()
        if not last:
            return "Not synced yet"

        from taskrepo.utils.time_format import format_time_ago

        time_str = format_time_ago(last.timestamp)

        if last.success:
            repo_count = len(last.repos_synced)
            if repo_count == 1:
                return f"Synced {time_str}"
            else:
                return f"Synced {time_str} ({repo_count} repos)"
        else:
            failed_count = len(last.repos_failed)
            if failed_count == 1:
                return f"Sync failed {time_str} (1 repo)"
            else:
                return f"Sync failed {time_str} ({failed_count} repos)"
