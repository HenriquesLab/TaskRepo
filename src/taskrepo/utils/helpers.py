"""Helper utility functions for TaskRepo."""

import click

from taskrepo.utils.id_mapping import get_uuid_from_display_id


def normalize_task_id(task_id: str) -> str:
    """Normalize a task ID, resolving display IDs to UUIDs.

    Tries to resolve display IDs (1, 2, 3...) to UUIDs using cache.
    If resolution fails, returns task_id as-is (could be UUID or legacy ID).

    Examples:
        "1" -> "a3f2e1d9-4b7c-4e3f-9a1b-2c3d4e5f6a7b" (if in cache)
        "42" -> "b4e3d2c1-5a6b-4c5d-8e7f-9a0b1c2d3e4f" (if in cache)
        "a3f2e1d9..." -> "a3f2e1d9..." (UUID, unchanged)

    Args:
        task_id: Task ID to normalize (display ID or UUID)

    Returns:
        UUID string if display ID resolved, otherwise original task_id
    """
    # Strip whitespace
    task_id = task_id.strip()

    # Check if it's a numeric display ID
    if task_id.isdigit():
        # Try to resolve display ID to UUID
        uuid = get_uuid_from_display_id(task_id)
        if uuid:
            return uuid

    # Return as-is (could be UUID or not found in cache)
    return task_id


def find_task_by_title_or_id(manager, task_identifier, repo=None):
    """Find a task by ID or title.

    Args:
        manager: RepositoryManager instance
        task_identifier: Task ID or title string
        repo: Optional repository name to search in

    Returns:
        Tuple of (task, repository) or (None, None) if not found
        If multiple matches, returns (list_of_tasks, list_of_repos)
    """
    # First, try to find by ID
    normalized_id = normalize_task_id(task_identifier)

    if repo:
        repository = manager.get_repository(repo)
        if repository:
            task = repository.get_task(normalized_id)
            if task:
                return task, repository
    else:
        # Search all repos by ID
        for r in manager.discover_repositories():
            t = r.get_task(normalized_id)
            if t:
                return t, r

    # If not found by ID, search by title
    matching_tasks = []
    matching_repos = []

    if repo:
        repository = manager.get_repository(repo)
        if repository:
            for task in repository.list_tasks():
                if task.title.lower() == task_identifier.lower():
                    matching_tasks.append(task)
                    matching_repos.append(repository)
    else:
        for r in manager.discover_repositories():
            for task in r.list_tasks():
                if task.title.lower() == task_identifier.lower():
                    matching_tasks.append(task)
                    matching_repos.append(r)

    if len(matching_tasks) == 0:
        return None, None
    elif len(matching_tasks) == 1:
        return matching_tasks[0], matching_repos[0]
    else:
        # Multiple matches - return lists
        return matching_tasks, matching_repos


def select_task_from_result(ctx, result, task_identifier):
    """Handle task lookup result and prompt user if multiple matches.

    This function centralizes the common pattern of handling results from
    find_task_by_title_or_id(), including error handling and user selection.

    Args:
        ctx: Click context (for exit)
        result: Tuple returned from find_task_by_title_or_id()
        task_identifier: The original task identifier (for error messages)

    Returns:
        Tuple of (task, repository) if found and selected
        Exits via ctx.exit() if not found or cancelled

    Example:
        result = find_task_by_title_or_id(manager, task_id, repo)
        task, repository = select_task_from_result(ctx, result, task_id)
    """
    if result[0] is None:
        # Not found
        click.secho(f"Error: No task found matching '{task_identifier}'", fg="red", err=True)
        ctx.exit(1)

    elif isinstance(result[0], list):
        # Multiple matches - ask user to select
        click.echo(f"\nMultiple tasks found matching '{task_identifier}':")
        for idx, (t, r) in enumerate(zip(result[0], result[1], strict=False), start=1):
            click.echo(f"  {idx}. [{t.id[:8]}...] {t.title} (repo: {r.name})")

        try:
            choice = click.prompt("\nSelect task number", type=int)
            if choice < 1 or choice > len(result[0]):
                click.secho("Invalid selection", fg="red", err=True)
                ctx.exit(1)
            task = result[0][choice - 1]
            repository = result[1][choice - 1]
        except (ValueError, click.Abort):
            click.echo("Cancelled.")
            ctx.exit(0)

    else:
        # Single match found
        task, repository = result

    return task, repository


def update_cache_and_display_repo(manager, repository, config):
    """Update ID cache and display repository tasks after a modification.

    This function centralizes the common pattern used after modifying tasks
    (add, edit, done, delete) to update the ID cache and display active tasks.

    Args:
        manager: RepositoryManager instance
        repository: Repository instance to display tasks from
        config: Config instance for sorting preferences

    Example:
        # After saving a task
        update_cache_and_display_repo(manager, repository, config)
    """
    from taskrepo.tui.display import display_tasks_table
    from taskrepo.utils.id_mapping import save_id_cache
    from taskrepo.utils.sorting import sort_tasks

    # Update cache with ALL active tasks across all repos (sorted)
    all_tasks_all_repos = manager.list_all_tasks()
    active_tasks_all = [t for t in all_tasks_all_repos if t.status != "completed"]
    sorted_tasks = sort_tasks(active_tasks_all, config)
    save_id_cache(sorted_tasks)

    # Display tasks from this repository only (filtered view)
    repo_tasks = repository.list_tasks()
    active_tasks_repo = [t for t in repo_tasks if t.status != "completed"]

    if active_tasks_repo:
        display_tasks_table(active_tasks_repo, config, save_cache=False)
