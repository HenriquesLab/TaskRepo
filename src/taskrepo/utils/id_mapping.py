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


def save_id_cache(tasks: list[Task], rebalance: bool = True) -> None:
    """Save display ID to UUID mapping cache.

    Args:
        tasks: List of tasks in display order
        rebalance: If True, reassign sequential IDs. If False, preserve existing IDs.
    """
    cache_path = get_cache_path()

    if rebalance:
        # Full rebalance: assign sequential IDs based on task order
        cache = {}
        for idx, task in enumerate(tasks, start=1):
            cache[str(idx)] = {
                "uuid": task.id,
                "repo": task.repo,
                "title": task.title,
            }
    else:
        # Stable mode: preserve existing IDs, assign new IDs to new tasks
        # Load existing cache
        existing_cache = {}
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    existing_cache = json.load(f)
            except (json.JSONDecodeError, KeyError):
                existing_cache = {}

        # Build UUID -> existing ID mapping
        uuid_to_id = {}
        for display_id, entry in existing_cache.items():
            uuid_to_id[entry["uuid"]] = int(display_id)

        # Find which IDs are currently used
        used_ids = set(uuid_to_id.values())

        # Find gaps (freed IDs)
        max_id = max(used_ids) if used_ids else 0
        all_possible_ids = set(range(1, max_id + 1))
        gaps = sorted(all_possible_ids - used_ids)

        # Build new cache
        cache = {}
        next_new_id = max_id + 1

        for task in tasks:
            if task.id in uuid_to_id:
                # Existing task: keep its ID
                display_id = uuid_to_id[task.id]
            else:
                # New task: fill gap or use next sequential ID
                if gaps:
                    display_id = gaps.pop(0)
                else:
                    display_id = next_new_id
                    next_new_id += 1

            cache[str(display_id)] = {
                "uuid": task.id,
                "repo": task.repo,
                "title": task.title,
            }

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
