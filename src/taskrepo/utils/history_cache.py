"""History cache management for accelerating git history queries.

This module provides persistent caching of commit history to dramatically speed up
repeated `tsk history` queries. Cache is stored per-repository and supports
incremental updates.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from taskrepo.core.repository import Repository
from taskrepo.utils.paths import get_history_cache_dir

# Cache format version - increment when structure changes
CACHE_VERSION = "1.0"


def get_cache_path(repo_name: str) -> Path:
    """Get the cache file path for a repository.

    Args:
        repo_name: Name of the repository

    Returns:
        Path to the cache file (e.g., ~/.TaskRepo/history_cache/rhenriques_commits.json)
    """
    cache_dir = get_history_cache_dir()
    # Sanitize repo name for filename
    safe_name = repo_name.replace("/", "_").replace("\\", "_")
    return cache_dir / f"{safe_name}_commits.json"


def load_cache(repo_name: str) -> Optional[dict]:
    """Load cache data from disk.

    Args:
        repo_name: Name of the repository

    Returns:
        Cache data dict, or None if cache doesn't exist or is invalid
    """
    cache_path = get_cache_path(repo_name)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate cache version
        if data.get("cache_version") != CACHE_VERSION:
            return None

        return data
    except (json.JSONDecodeError, IOError, KeyError):
        # Cache file is corrupt or unreadable - ignore it
        return None


def save_cache(repo_name: str, repo_path: str, commits: list[dict]) -> None:
    """Save cache data to disk.

    Args:
        repo_name: Name of the repository
        repo_path: Absolute path to the repository
        commits: List of commit dicts to cache (sorted newest first)
    """
    if not commits:
        return

    cache_data = {
        "cache_version": CACHE_VERSION,
        "repo_path": str(repo_path),
        "last_commit_hash": commits[0]["commit_hash"],  # Newest commit
        "last_commit_date": commits[0]["timestamp"],
        "commit_count": len(commits),
        "commits": commits,
    }

    cache_path = get_cache_path(repo_name)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
    except IOError:
        # If we can't write cache, just continue without caching
        pass


def is_cache_valid(repo: Repository, cache_data: dict) -> bool:
    """Check if cached data is up-to-date with repository.

    Args:
        repo: Repository object
        cache_data: Loaded cache data

    Returns:
        True if cache is valid, False if outdated
    """
    if not repo.git_repo:
        return False

    try:
        # Get current HEAD commit hash
        current_head = repo.git_repo.head.commit.hexsha
        cached_head = cache_data.get("last_commit_hash")

        # Cache is valid if HEAD hasn't changed
        # Compare first 8 chars since we store short hashes
        return current_head.startswith(cached_head) or current_head == cached_head
    except Exception:
        # If we can't get HEAD, assume cache is invalid
        return False


def get_cached_commits(
    repo: Repository,
    since: Optional[datetime] = None,
    use_cache: bool = True,
) -> Optional[list[dict]]:
    """Retrieve commits from cache if available and valid.

    Args:
        repo: Repository object
        since: Optional datetime to filter commits (only return commits after this date)
        use_cache: If False, always return None (bypass cache)

    Returns:
        List of cached commit dicts, or None if cache miss
    """
    if not use_cache:
        return None

    cache_data = load_cache(repo.name)

    if cache_data is None:
        return None

    # Check if cache is still valid
    if not is_cache_valid(repo, cache_data):
        return None

    commits = cache_data.get("commits", [])

    # Filter by date if requested
    if since:
        filtered_commits = []
        for commit in commits:
            commit_time = datetime.fromisoformat(commit["timestamp"])
            # Make timezone-naive for comparison (since is always naive from parse_date_or_duration)
            if commit_time.tzinfo is not None:
                commit_time = commit_time.replace(tzinfo=None)
            if commit_time >= since:
                filtered_commits.append(commit)
        return filtered_commits

    return commits


def update_cache_incremental(
    repo: Repository,
    new_commits: list[dict],
) -> None:
    """Update cache with new commits (incremental update).

    Args:
        repo: Repository object
        new_commits: List of new commit dicts to add (sorted newest first)
    """
    if not new_commits:
        return

    cache_data = load_cache(repo.name)

    if cache_data is None:
        # No existing cache - create new one
        save_cache(repo.name, repo.path, new_commits)
        return

    # Merge new commits with cached commits
    cached_commits = cache_data.get("commits", [])

    # Remove duplicates (in case of cache inconsistency)
    new_hashes = {c["commit_hash"] for c in new_commits}
    cached_commits = [c for c in cached_commits if c["commit_hash"] not in new_hashes]

    # Combine: new commits first (newest), then cached commits
    all_commits = new_commits + cached_commits

    # Save updated cache
    save_cache(repo.name, repo.path, all_commits)


def clear_cache(repo_name: Optional[str] = None) -> int:
    """Clear history cache.

    Args:
        repo_name: Optional specific repository to clear. If None, clears all caches.

    Returns:
        Number of cache files deleted
    """
    cache_dir = get_history_cache_dir()

    if repo_name:
        # Clear specific repo cache
        cache_path = get_cache_path(repo_name)
        if cache_path.exists():
            cache_path.unlink()
            return 1
        return 0
    else:
        # Clear all caches
        if not cache_dir.exists():
            return 0

        count = 0
        for cache_file in cache_dir.glob("*_commits.json"):
            cache_file.unlink()
            count += 1
        return count


def get_cache_stats() -> dict:
    """Get statistics about cached data.

    Returns:
        Dict with cache statistics (total files, total commits, total size)
    """
    cache_dir = get_history_cache_dir()

    if not cache_dir.exists():
        return {"cache_files": 0, "total_commits": 0, "total_size_bytes": 0}

    total_commits = 0
    total_size = 0
    cache_files = list(cache_dir.glob("*_commits.json"))

    for cache_file in cache_files:
        total_size += cache_file.stat().st_size
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                total_commits += data.get("commit_count", 0)
        except (json.JSONDecodeError, IOError):
            pass

    return {
        "cache_files": len(cache_files),
        "total_commits": total_commits,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
    }
