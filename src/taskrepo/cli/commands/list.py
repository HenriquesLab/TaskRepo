"""List command for displaying tasks."""

import json
from pathlib import Path

import click
from rich.console import Console

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table
from taskrepo.utils.conflict_detection import display_conflict_warning, scan_all_repositories
from taskrepo.utils.id_mapping import get_cache_path


def _load_uuid_to_display_id() -> dict[str, int]:
    """Load the ID cache once and return a {uuid: display_id} map.

    Returns an empty dict if the cache file is missing, unreadable, or
    structurally unexpected (e.g. top-level non-object, entries missing
    ``uuid``). Callers that care about missing cache state should check the
    returned dict length.
    """
    cache_path = get_cache_path()
    if not cache_path.exists():
        return {}
    try:
        with open(cache_path) as f:
            cache = json.load(f)
        if not isinstance(cache, dict):
            return {}
        return {
            entry["uuid"]: int(display_id)
            for display_id, entry in cache.items()
            if isinstance(entry, dict) and "uuid" in entry
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return {}


def _task_to_dict(task, uuid_to_id: dict[str, int]) -> dict:
    """Serialize a Task to a JSON-compatible dict.

    ``id`` is the short numeric display ID matching the table view, or ``null``
    if the task isn't in the ID cache (e.g. freshly added or on a fresh clone
    before ``tsk list`` has populated the cache). ``uuid`` is always the
    stable underlying identifier. All dates are ISO 8601.
    """
    return {
        "id": uuid_to_id.get(task.id),
        "uuid": task.id,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "repo": task.repo,
        "project": task.project,
        "assignees": list(task.assignees),
        "tags": list(task.tags),
        "links": list(task.links),
        "due": task.due.isoformat() if task.due else None,
        "created": task.created.isoformat() if task.created else None,
        "modified": task.modified.isoformat() if task.modified else None,
        "depends": list(task.depends),
        "parent": task.parent,
        "description": task.description,
    }


@click.command(name="list")
@click.option("--repo", "-r", help="Filter by repository")
@click.option("--project", "-p", help="Filter by project")
@click.option("--status", "-s", help="Filter by status")
@click.option("--priority", type=click.Choice(["H", "M", "L"], case_sensitive=False), help="Filter by priority")
@click.option("--assignee", "-a", help="Filter by assignee")
@click.option("--tag", "-t", help="Filter by tag")
@click.option("--archived", is_flag=True, help="Show archived tasks")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON (machine-readable, no truncation)")
@click.pass_context
def list_tasks(ctx, repo, project, status, priority, assignee, tag, archived, json_output):
    """List tasks with optional filters.

    By default, shows all non-archived tasks (including completed).
    Use --archived to show archived tasks instead.
    Use --json for machine-readable output suitable for scripting or LLMs.
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Check for unresolved merge conflicts and warn user.
    # In JSON mode, emit the warning to stderr so stdout stays valid JSON.
    conflicts = scan_all_repositories(Path(config.parent_dir).expanduser())
    if conflicts:
        console = Console(stderr=True) if json_output else Console()
        display_conflict_warning(conflicts, console)

    # Get tasks (including or excluding archived based on flag)
    if repo:
        repository = manager.get_repository(repo)
        if not repository:
            click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
            ctx.exit(1)
        if archived:
            tasks = repository.list_archived_tasks()
        else:
            tasks = repository.list_tasks(include_archived=False)
    else:
        if archived:
            # Get archived tasks from all repos
            tasks = []
            for r in manager.discover_repositories():
                tasks.extend(r.list_archived_tasks())
        else:
            tasks = manager.list_all_tasks(include_archived=False)

    # Track if any filters are applied
    has_filters = bool(repo or project or status or priority or assignee or tag or archived)

    # Keep reference to all tasks for effective due date calculation
    all_tasks = tasks.copy()

    # Apply filters (no automatic exclusion of completed tasks)

    if project:
        tasks = [t for t in tasks if t.project == project]

    if status:
        tasks = [t for t in tasks if t.status == status]

    if priority:
        tasks = [t for t in tasks if t.priority.upper() == priority.upper()]

    if assignee:
        if not assignee.startswith("@"):
            assignee = f"@{assignee}"
        tasks = [t for t in tasks if assignee in t.assignees]

    if tag:
        tasks = [t for t in tasks if tag in t.tags]

    # Display results
    if not tasks:
        if json_output:
            click.echo("[]")
        else:
            click.echo("No tasks found.")
        return

    # Sort tasks before display (always sort, regardless of filters)
    from taskrepo.utils.id_mapping import save_id_cache
    from taskrepo.utils.sorting import sort_tasks

    sorted_tasks = sort_tasks(tasks, config, all_tasks=all_tasks)

    # Only rebalance IDs for unfiltered views (like sync does).
    # Do this before serializing so JSON short IDs match the table view.
    if not has_filters:
        save_id_cache(sorted_tasks, rebalance=True)

    if json_output:
        # Load the UUID→display_id map once to avoid O(n²) disk reads.
        # On unfiltered runs, save_id_cache() above has already populated
        # the cache, so uuid_to_id will not be empty below.
        uuid_to_id = _load_uuid_to_display_id()
        # Emit a one-time hint if the cache is empty on a filtered view —
        # every JSON id will be null until `tsk list` is run unfiltered.
        if not uuid_to_id and has_filters:
            click.echo(
                "Note: ID cache is empty; `id` fields will be null. "
                "Run `tsk list` without filters once to populate it.",
                err=True,
            )
        payload = [_task_to_dict(t, uuid_to_id) for t in sorted_tasks]
        click.echo(json.dumps(payload, indent=2, default=str))
        return

    # Display sorted tasks
    display_tasks_table(sorted_tasks, config, save_cache=False)
