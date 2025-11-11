"""Configuration management for TaskRepo."""

from pathlib import Path
from typing import Optional

import yaml

from taskrepo.utils.paths import get_config_path, migrate_legacy_files


class Config:
    """Manages TaskRepo configuration.

    Configuration is stored in ~/.TaskRepo/config as YAML.
    Legacy config at ~/.taskreporc is automatically migrated.
    """

    DEFAULT_CONFIG = {
        "parent_dir": "~/tasks",
        "default_priority": "M",
        "default_status": "pending",
        "default_assignee": None,
        "default_github_org": None,
        "default_repo": None,
        "default_editor": None,
        "sort_by": ["due", "priority"],
        "cluster_due_dates": False,
        "tui_view_mode": "repo",  # Options: "repo", "project", "assignee"
        "auto_sync_enabled": True,  # Enable background sync in TUI
        "auto_sync_interval": 300,  # Sync every 5 minutes (in seconds)
        "auto_sync_strategy": "auto",  # Auto-merge strategy for background sync
    }

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize Config.

        Args:
            config_path: Path to config file (defaults to ~/.TaskRepo/config)
        """
        # Migrate legacy files on first access
        migrate_legacy_files()

        if config_path is None:
            config_path = get_config_path()

        self.config_path = config_path
        self._data = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from file.

        Returns:
            Configuration dictionary
        """
        if not self.config_path.exists():
            # Create default config
            self._data = self.DEFAULT_CONFIG.copy()
            self.save()
            return self._data

        try:
            with open(self.config_path) as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            print(f"Warning: Failed to parse config file: {e}")
            data = {}

        # Merge with defaults
        config = self.DEFAULT_CONFIG.copy()
        config.update(data)
        return config

    def save(self):
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump(self._data, f, default_flow_style=False, sort_keys=False)

    @property
    def parent_dir(self) -> Path:
        """Get parent directory for task repositories.

        Returns:
            Path to parent directory
        """
        return Path(self._data["parent_dir"]).expanduser()

    @parent_dir.setter
    def parent_dir(self, value: Path):
        """Set parent directory for task repositories.

        Args:
            value: Path to parent directory
        """
        self._data["parent_dir"] = str(value)
        self.save()

    @property
    def default_priority(self) -> str:
        """Get default task priority.

        Returns:
            Default priority (H, M, or L)
        """
        return self._data["default_priority"]

    @default_priority.setter
    def default_priority(self, value: str):
        """Set default task priority.

        Args:
            value: Default priority (H, M, or L)
        """
        if value not in {"H", "M", "L"}:
            raise ValueError(f"Invalid priority: {value}")
        self._data["default_priority"] = value
        self.save()

    @property
    def default_status(self) -> str:
        """Get default task status.

        Returns:
            Default status
        """
        return self._data["default_status"]

    @default_status.setter
    def default_status(self, value: str):
        """Set default task status.

        Args:
            value: Default status
        """
        self._data["default_status"] = value
        self.save()

    @property
    def default_assignee(self) -> Optional[str]:
        """Get default task assignee.

        Returns:
            Default assignee handle (with @ prefix) or None
        """
        return self._data.get("default_assignee")

    @default_assignee.setter
    def default_assignee(self, value: Optional[str]):
        """Set default task assignee.

        Args:
            value: Default assignee handle (will add @ prefix if missing) or None
        """
        if value is not None and value.strip():
            # Ensure @ prefix
            value = value.strip()
            if not value.startswith("@"):
                value = f"@{value}"
            self._data["default_assignee"] = value
        else:
            self._data["default_assignee"] = None
        self.save()

    @property
    def default_github_org(self) -> Optional[str]:
        """Get default GitHub organization/owner.

        Returns:
            Default GitHub organization/owner or None
        """
        return self._data.get("default_github_org")

    @default_github_org.setter
    def default_github_org(self, value: Optional[str]):
        """Set default GitHub organization/owner.

        Args:
            value: Default GitHub organization/owner or None
        """
        if value is not None and value.strip():
            self._data["default_github_org"] = value.strip()
        else:
            self._data["default_github_org"] = None
        self.save()

    @property
    def default_repo(self) -> Optional[str]:
        """Get default repository name.

        Returns:
            Default repository name (without 'tasks-' prefix) or None
        """
        return self._data.get("default_repo")

    @default_repo.setter
    def default_repo(self, value: Optional[str]):
        """Set default repository name.

        Args:
            value: Default repository name (without 'tasks-' prefix) or None
        """
        if value is not None and value.strip():
            self._data["default_repo"] = value.strip()
        else:
            self._data["default_repo"] = None
        self.save()

    @property
    def default_editor(self) -> Optional[str]:
        """Get default text editor.

        Returns:
            Default editor command or None
        """
        return self._data.get("default_editor")

    @default_editor.setter
    def default_editor(self, value: Optional[str]):
        """Set default text editor.

        Args:
            value: Editor command (e.g., 'vim', 'nano', 'code') or None
        """
        if value is not None and value.strip():
            self._data["default_editor"] = value.strip()
        else:
            self._data["default_editor"] = None
        self.save()

    @property
    def sort_by(self) -> list[str]:
        """Get task sorting fields.

        Returns:
            List of sort field names
        """
        return self._data.get("sort_by", ["priority", "due"])

    @sort_by.setter
    def sort_by(self, value: list[str]):
        """Set task sorting fields.

        Args:
            value: List of sort field names

        Raises:
            ValueError: If invalid sort field provided
        """
        import re

        valid_fields = {
            "priority",
            "due",
            "urgency",
            "created",
            "modified",
            "status",
            "title",
            "project",
            "assignee",
            "-priority",
            "-due",
            "-urgency",
            "-created",
            "-modified",
            "-status",
            "-title",
            "-project",
            "-assignee",
        }

        # Pattern for assignee with preferred user: assignee:@username or -assignee:@username
        assignee_pattern = re.compile(r"^-?assignee(?::@\w+)?$")

        for field in value:
            # Check if it's a standard valid field
            if field in valid_fields:
                continue

            # Check if it matches the assignee:@username pattern
            if assignee_pattern.match(field):
                continue

            # If we get here, it's an invalid field
            raise ValueError(
                f"Invalid sort field: {field}. Must be one of {valid_fields} or match pattern 'assignee:@username'"
            )

        self._data["sort_by"] = value
        self.save()

    @property
    def cluster_due_dates(self) -> bool:
        """Get due date clustering setting.

        Returns:
            True if tasks should be clustered by countdown buckets instead of exact timestamps
        """
        return self._data.get("cluster_due_dates", False)

    @cluster_due_dates.setter
    def cluster_due_dates(self, value: bool):
        """Set due date clustering.

        Args:
            value: True to cluster tasks by countdown buckets (today, this week, etc.)
        """
        self._data["cluster_due_dates"] = bool(value)
        self.save()

    @property
    def tui_view_mode(self) -> str:
        """Get TUI view mode.

        Returns:
            View mode: "repo", "project", or "assignee"
        """
        return self._data.get("tui_view_mode", "repo")

    @tui_view_mode.setter
    def tui_view_mode(self, value: str):
        """Set TUI view mode.

        Args:
            value: View mode ("repo", "project", or "assignee")

        Raises:
            ValueError: If invalid view mode provided
        """
        valid_modes = {"repo", "project", "assignee"}
        if value not in valid_modes:
            raise ValueError(f"Invalid TUI view mode: {value}. Must be one of {valid_modes}")
        self._data["tui_view_mode"] = value
        self.save()

    @property
    def auto_sync_enabled(self) -> bool:
        """Get automatic sync enabled status.

        Returns:
            True if background sync is enabled in TUI
        """
        return self._data.get("auto_sync_enabled", True)

    @auto_sync_enabled.setter
    def auto_sync_enabled(self, value: bool):
        """Set automatic sync enabled status.

        Args:
            value: True to enable background sync in TUI
        """
        self._data["auto_sync_enabled"] = bool(value)
        self.save()

    @property
    def auto_sync_interval(self) -> int:
        """Get automatic sync interval in seconds.

        Returns:
            Sync interval in seconds (default: 300 = 5 minutes)
        """
        return self._data.get("auto_sync_interval", 300)

    @auto_sync_interval.setter
    def auto_sync_interval(self, value: int):
        """Set automatic sync interval.

        Args:
            value: Sync interval in seconds (minimum: 60)

        Raises:
            ValueError: If interval is less than 60 seconds
        """
        if value < 60:
            raise ValueError("Sync interval must be at least 60 seconds")
        self._data["auto_sync_interval"] = int(value)
        self.save()

    @property
    def auto_sync_strategy(self) -> str:
        """Get automatic sync strategy.

        Returns:
            Sync strategy for background sync (default: "auto")
        """
        return self._data.get("auto_sync_strategy", "auto")

    @auto_sync_strategy.setter
    def auto_sync_strategy(self, value: str):
        """Set automatic sync strategy.

        Args:
            value: Sync strategy ("auto", "local", or "remote")

        Raises:
            ValueError: If invalid strategy provided
        """
        valid_strategies = {"auto", "local", "remote"}
        if value not in valid_strategies:
            raise ValueError(f"Invalid sync strategy: {value}. Must be one of {valid_strategies}")
        self._data["auto_sync_strategy"] = value
        self.save()

    def get(self, key: str, default=None):
        """Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        return self._data.get(key, default)

    def set(self, key: str, value):
        """Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self._data[key] = value
        self.save()
