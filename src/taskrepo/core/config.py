"""Configuration management for TaskRepo."""

from pathlib import Path
from typing import Optional

import yaml


class Config:
    """Manages TaskRepo configuration.

    Configuration is stored in ~/.taskreporc as YAML.
    """

    DEFAULT_CONFIG = {
        "parent_dir": "~/tasks",
        "default_priority": "M",
        "default_status": "pending",
        "default_assignee": None,
        "default_github_org": None,
        "default_editor": None,
        "sort_by": ["priority", "due"],
    }

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize Config.

        Args:
            config_path: Path to config file (defaults to ~/.taskreporc)
        """
        if config_path is None:
            config_path = Path.home() / ".taskreporc"

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
        valid_fields = {
            "priority",
            "due",
            "created",
            "modified",
            "status",
            "title",
            "project",
            "-priority",
            "-due",
            "-created",
            "-modified",
            "-status",
            "-title",
            "-project",
        }

        for field in value:
            if field not in valid_fields:
                raise ValueError(f"Invalid sort field: {field}. Must be one of {valid_fields}")

        self._data["sort_by"] = value
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
