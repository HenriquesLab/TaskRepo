"""Helper utility functions for TaskRepo."""

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
