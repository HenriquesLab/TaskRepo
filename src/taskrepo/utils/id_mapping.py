"""ID mapping utilities for display ID to UUID conversion."""

import json
from pathlib import Path
from typing import Optional

from taskrepo.core.task import Task
from taskrepo.utils.paths import get_id_cache_path, migrate_legacy_files


def get_cache_path() -> Path:
    """Get the path to the ID mapping cache file.

    Returns:
        Path to cache file (~/.TaskRepo/id_cache.json)
    """
    # Ensure legacy files are migrated
    migrate_legacy_files()
    return get_id_cache_path()


def save_id_cache(tasks: list[Task]) -> None:
    """Save display ID to UUID mapping cache.

    Args:
        tasks: List of tasks in display order
    """
    cache = {}
    for idx, task in enumerate(tasks, start=1):
        cache[str(idx)] = {
            "uuid": task.id,
            "repo": task.repo,
            "title": task.title,
        }

    cache_path = get_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)


def get_uuid_from_display_id(display_id: str) -> Optional[str]:
    """Get UUID from display ID using cache.

    Args:
        display_id: Display ID (e.g., "1", "2", "3")

    Returns:
        UUID string if found, None otherwise
    """
    cache_path = get_cache_path()
    if not cache_path.exists():
        return None

    try:
        with open(cache_path) as f:
            cache = json.load(f)

        entry = cache.get(str(display_id))
        if entry:
            return entry["uuid"]
    except (json.JSONDecodeError, KeyError):
        return None

    return None


def clear_id_cache() -> None:
    """Clear the ID mapping cache."""
    cache_path = get_cache_path()
    if cache_path.exists():
        cache_path.unlink()


def get_display_id_from_uuid(uuid: str) -> Optional[int]:
    """Get display ID from UUID using cache.

    Args:
        uuid: UUID string

    Returns:
        Display ID as integer if found, None otherwise
    """
    cache_path = get_cache_path()
    if not cache_path.exists():
        return None

    try:
        with open(cache_path) as f:
            cache = json.load(f)

        for display_id, entry in cache.items():
            if entry["uuid"] == uuid:
                return int(display_id)
    except (json.JSONDecodeError, KeyError, ValueError):
        return None

    return None


def get_cache_size() -> int:
    """Get the number of tasks in the ID cache.

    Returns:
        Number of tasks in cache, or 0 if cache doesn't exist or is invalid
    """
    cache_path = get_cache_path()
    if not cache_path.exists():
        return 0

    try:
        with open(cache_path) as f:
            cache = json.load(f)
        return len(cache)
    except (json.JSONDecodeError, KeyError):
        return 0
