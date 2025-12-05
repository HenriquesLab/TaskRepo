"""Path management utilities for TaskRepo configuration and cache files."""

from pathlib import Path


def get_taskrepo_dir() -> Path:
    """Get the TaskRepo configuration directory.

    Returns:
        Path to ~/.TaskRepo/
    """
    return Path.home() / ".TaskRepo"


def get_config_path() -> Path:
    """Get the path to the configuration file.

    Returns:
        Path to ~/.TaskRepo/config
    """
    return get_taskrepo_dir() / "config"


def get_id_cache_path() -> Path:
    """Get the path to the ID mapping cache file.

    Returns:
        Path to ~/.TaskRepo/id_cache.json
    """
    return get_taskrepo_dir() / "id_cache.json"


def get_update_check_cache_path() -> Path:
    """Get the path to the update check cache file.

    Returns:
        Path to ~/.TaskRepo/update_check_cache.json
    """
    return get_taskrepo_dir() / "update_check_cache.json"


def get_history_cache_dir() -> Path:
    """Get the path to the history cache directory.

    Returns:
        Path to ~/.TaskRepo/history_cache/
    """
    cache_dir = get_taskrepo_dir() / "history_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_legacy_config_path() -> Path:
    """Get the path to the legacy configuration file.

    Returns:
        Path to ~/.taskreporc
    """
    return Path.home() / ".taskreporc"


def get_legacy_id_cache_path() -> Path:
    """Get the path to the legacy ID cache file.

    Returns:
        Path to ~/.taskrepo_id_cache.json
    """
    return Path.home() / ".taskrepo_id_cache.json"


def get_legacy_update_check_cache_path() -> Path:
    """Get the path to the legacy update check cache file.

    Returns:
        Path to ~/.taskrepo_update_check.json
    """
    return Path.home() / ".taskrepo_update_check.json"


def migrate_legacy_files() -> None:
    """Migrate legacy config and cache files to new location.

    Moves files from:
    - ~/.taskreporc -> ~/.TaskRepo/config
    - ~/.taskrepo_id_cache.json -> ~/.TaskRepo/id_cache.json
    - ~/.taskrepo_update_check.json -> ~/.TaskRepo/update_check_cache.json
    """
    taskrepo_dir = get_taskrepo_dir()
    taskrepo_dir.mkdir(parents=True, exist_ok=True)

    # Migrate config file
    legacy_config = get_legacy_config_path()
    new_config = get_config_path()
    if legacy_config.exists() and not new_config.exists():
        legacy_config.rename(new_config)

    # Migrate ID cache
    legacy_id_cache = get_legacy_id_cache_path()
    new_id_cache = get_id_cache_path()
    if legacy_id_cache.exists() and not new_id_cache.exists():
        legacy_id_cache.rename(new_id_cache)

    # Migrate update check cache
    legacy_update_cache = get_legacy_update_check_cache_path()
    new_update_cache = get_update_check_cache_path()
    if legacy_update_cache.exists() and not new_update_cache.exists():
        legacy_update_cache.rename(new_update_cache)
