"""Helper utility functions for TaskRepo."""

from typing import Any, Callable, List, Optional, Tuple

import click
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.validation import Validator

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


def process_tasks_batch(
    ctx,
    manager,
    task_ids: Tuple[str, ...],
    repo: Optional[str],
    task_handler: Callable[[Any, Any], Tuple[bool, Optional[str]]],
    operation_name: str = "processed",
) -> Tuple[List[Tuple[Any, Any]], List[str]]:
    """Generic batch task processor that centralizes common patterns.

    This function handles the common batch processing pattern used across multiple commands:
    - Flattens comma-separated task IDs
    - Finds tasks by ID or title
    - Handles not found / multiple matches
    - Batch mode error handling
    - Success/failure tracking

    Args:
        ctx: Click context (for exit)
        manager: RepositoryManager instance
        task_ids: Tuple of task IDs from command argument
        repo: Optional repository name to limit search
        task_handler: Callback function that processes each task.
                     Should take (task, repository) and return (success: bool, message: Optional[str])
                     If success=False, the message is shown as an error.
        operation_name: Name of operation for summary messages (e.g., "completed", "deleted")

    Returns:
        Tuple of (successful_results, failed_ids) where:
        - successful_results: List of (task, repository) tuples that were processed
        - failed_ids: List of task_id strings that failed

    Example:
        def mark_as_done(task, repository):
            task.status = "completed"
            repository.save_task(task)
            return True, None

        results, failures = process_tasks_batch(
            ctx, manager, task_ids, repo,
            task_handler=mark_as_done,
            operation_name="completed"
        )
    """
    # Flatten comma-separated task IDs (supports both "4 5 6" and "4,5,6")
    task_id_list = []
    for task_id in task_ids:
        task_id_list.extend([tid.strip() for tid in task_id.split(",")])

    is_batch = len(task_id_list) > 1

    # Track results
    successful_results = []
    failed_tasks = []

    for task_id in task_id_list:
        try:
            # Try to find task by ID or title
            result = find_task_by_title_or_id(manager, task_id, repo)

            # Handle not found
            if result[0] is None:
                if is_batch:
                    click.secho(f"✗ No task found matching '{task_id}'", fg="red")
                    failed_tasks.append(task_id)
                    continue
                else:
                    click.secho(f"Error: No task found matching '{task_id}'", fg="red", err=True)
                    ctx.exit(1)

            # Handle multiple matches
            elif isinstance(result[0], list):
                if is_batch:
                    click.secho(f"✗ Multiple tasks found matching '{task_id}' - skipping", fg="red")
                    failed_tasks.append(task_id)
                    continue
                else:
                    # Let select_task_from_result handle the interactive selection
                    task, repository = select_task_from_result(ctx, result, task_id)
            else:
                # Single match found
                task, repository = result

            # Execute the task-specific handler
            success, error_msg = task_handler(task, repository)

            if success:
                successful_results.append((task, repository))
            else:
                failed_tasks.append(task_id)
                if error_msg:
                    if is_batch:
                        click.secho(f"✗ {error_msg}", fg="red")
                    else:
                        click.secho(f"Error: {error_msg}", fg="red", err=True)
                        ctx.exit(1)

        except Exception as e:
            # Unexpected error - show message and continue with next task
            failed_tasks.append(task_id)
            if is_batch:
                click.secho(f"✗ Could not process task '{task_id}': {e}", fg="red")
            else:
                click.secho(f"Error: Could not process task '{task_id}': {e}", fg="red", err=True)
                ctx.exit(1)

    # Show summary for batch operations
    if is_batch and successful_results:
        click.echo()
        click.secho(
            f"{operation_name.capitalize()} {len(successful_results)} of {len(task_id_list)} tasks",
            fg="green",
        )

    return successful_results, failed_tasks


def update_cache_and_display_repo(manager, repository, config):
    """Update ID cache and display repository tasks after a modification.

    This function centralizes the common pattern used after modifying tasks
    (add, edit, done, delete, archive) to update the ID cache and display tasks.

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

    # Update cache with ALL non-archived tasks across all repos (sorted)
    # Use stable mode (rebalance=False) to preserve IDs
    all_tasks_all_repos = manager.list_all_tasks(include_archived=False)
    sorted_tasks = sort_tasks(all_tasks_all_repos, config, all_tasks=all_tasks_all_repos)
    save_id_cache(sorted_tasks, rebalance=False)

    # Display tasks from this repository only (filtered view, excluding archived)
    repo_tasks = repository.list_tasks(include_archived=False)

    if repo_tasks:
        # Sort the repo tasks before displaying (using same sort order as global cache)
        sorted_repo_tasks = sort_tasks(repo_tasks, config, all_tasks=all_tasks_all_repos)
        display_tasks_table(sorted_repo_tasks, config, save_cache=False)


def prompt_for_subtask_archiving(manager, task, batch_mode=False):
    """Prompt user to archive subtasks when archiving a parent task.

    Args:
        manager: RepositoryManager instance
        task: The parent task being archived
        batch_mode: If True, skip prompting (used for batch operations)

    Returns:
        Number of subtasks archived
    """
    from taskrepo.utils.display_constants import STATUS_EMOJIS

    subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)

    if not subtasks_with_repos or batch_mode:
        return 0

    count = len(subtasks_with_repos)
    subtask_word = "subtask" if count == 1 else "subtasks"

    click.echo(f"\nThis task has {count} {subtask_word}:")
    for subtask, subtask_repo in subtasks_with_repos:
        status_emoji = STATUS_EMOJIS.get(subtask.status, "")
        click.echo(f"  • {status_emoji} {subtask.title} (repo: {subtask_repo.name})")

    # Prompt for confirmation with Y as default
    yn_validator = Validator.from_callable(
        lambda text: text.lower() in ["y", "n", "yes", "no"],
        error_message="Please enter 'y' or 'n'",
        move_cursor_to_end=True,
    )

    response = prompt(
        f"Mark all {count} {subtask_word} as completed too? (Y/n) ",
        default="y",
        validator=yn_validator,
    ).lower()

    if response in ["y", "yes"]:
        # Mark all subtasks as completed
        completed_count = 0
        for subtask, subtask_repo in subtasks_with_repos:
            if subtask.status != "completed":  # Only if not already completed
                subtask.status = "completed"
                subtask_repo.save_task(subtask)
                completed_count += 1

        if completed_count > 0:
            click.secho(f"✓ Marked {completed_count} {subtask_word} as completed", fg="green")
        return completed_count

    return 0


def prompt_for_subtask_unarchiving(manager, task, new_status, batch_mode=False):
    """Prompt user to unarchive subtasks when unarchiving a parent task.

    Args:
        manager: RepositoryManager instance
        task: The parent task being unarchived
        new_status: The new status to set for subtasks
        batch_mode: If True, skip prompting (used for batch operations)

    Returns:
        Number of subtasks unarchived
    """
    from taskrepo.utils.display_constants import STATUS_EMOJIS

    subtasks_with_repos = manager.get_all_subtasks_cross_repo(task.id)

    if not subtasks_with_repos or batch_mode:
        return 0

    # Filter to only completed subtasks
    completed_subtasks = [(st, repo) for st, repo in subtasks_with_repos if st.status == "completed"]

    if not completed_subtasks:
        return 0

    count = len(completed_subtasks)
    subtask_word = "subtask" if count == 1 else "subtasks"

    click.echo(f"\nThis task has {count} completed {subtask_word}:")
    for subtask, subtask_repo in completed_subtasks:
        status_emoji = STATUS_EMOJIS.get(subtask.status, "")
        click.echo(f"  • {status_emoji} {subtask.title} (repo: {subtask_repo.name})")

    # Prompt for confirmation with Y as default
    yn_validator = Validator.from_callable(
        lambda text: text.lower() in ["y", "n", "yes", "no"],
        error_message="Please enter 'y' or 'n'",
        move_cursor_to_end=True,
    )

    response = prompt(
        f"Mark {count} completed {subtask_word} as '{new_status}' too? (Y/n) ",
        default="y",
        validator=yn_validator,
    ).lower()

    if response in ["y", "yes"]:
        # Mark all completed subtasks with new status
        updated_count = 0
        for subtask, subtask_repo in completed_subtasks:
            subtask.status = new_status
            subtask_repo.save_task(subtask)
            updated_count += 1

        if updated_count > 0:
            click.secho(f"✓ Marked {updated_count} {subtask_word} as {new_status}", fg="green")
        return updated_count

    return 0


def parse_assignees(assignees_str: str) -> List[str]:
    """Parse comma-separated assignees string into list with @ prefix.

    Args:
        assignees_str: Comma-separated assignees (e.g., "alice,@bob,charlie")

    Returns:
        List of assignees with @ prefix (e.g., ["@alice", "@bob", "@charlie"])

    Example:
        >>> parse_assignees("alice,@bob")
        ['@alice', '@@bob']
        >>> parse_assignees("@alice, bob, charlie")
        ['@alice', '@bob', '@charlie']
    """
    if not assignees_str:
        return []

    assignees_list = [a.strip() for a in assignees_str.split(",") if a.strip()]
    # Ensure @ prefix
    assignees_list = [a if a.startswith("@") else f"@{a}" for a in assignees_list]
    return assignees_list


def parse_tags(tags_str: str) -> List[str]:
    """Parse comma-separated tags string into list.

    Args:
        tags_str: Comma-separated tags (e.g., "urgent,bug,frontend")

    Returns:
        List of tags (e.g., ["urgent", "bug", "frontend"])

    Example:
        >>> parse_tags("urgent, bug, frontend")
        ['urgent', 'bug', 'frontend']
        >>> parse_tags("")
        []
    """
    if not tags_str:
        return []

    return [t.strip() for t in tags_str.split(",") if t.strip()]


def parse_links(links_str: str) -> List[str]:
    """Parse comma-separated links string into list.

    Note: This function does NOT validate URLs. Validation should be done
    separately using Task.validate_url() if needed.

    Args:
        links_str: Comma-separated URLs (e.g., "https://github.com/...,https://...")

    Returns:
        List of URLs (e.g., ["https://github.com/...", "https://..."])

    Example:
        >>> parse_links("https://github.com/user/repo, https://example.com")
        ['https://github.com/user/repo', 'https://example.com']
        >>> parse_links("")
        []
    """
    if not links_str:
        return []

    return [link.strip() for link in links_str.split(",") if link.strip()]
