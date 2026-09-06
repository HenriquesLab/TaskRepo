from taskrepo.core.task import Task
from taskrepo.utils.dependencies import (
    build_task_lookup,
    filter_blocked_tasks,
    filter_ready_tasks,
    is_task_blocked,
    is_task_ready,
)


def _make_task(uuid: str, status: str = "pending", depends: list[str] = None) -> Task:
    return Task(
        id=uuid,
        title=f"Task {uuid}",
        status=status,
        priority="M",
        depends=depends or [],
    )


def test_task_with_no_dependencies_is_ready():
    task = _make_task("t1", status="pending")
    lookup = build_task_lookup([task])
    assert is_task_ready(task, lookup) is True
    assert is_task_blocked(task, lookup) is False


def test_completed_or_cancelled_task_is_not_ready():
    t_done = _make_task("t1", status="completed")
    t_canc = _make_task("t2", status="cancelled")
    lookup = build_task_lookup([t_done, t_canc])
    assert is_task_ready(t_done, lookup) is False
    assert is_task_ready(t_canc, lookup) is False
    assert is_task_blocked(t_done, lookup) is False
    assert is_task_blocked(t_canc, lookup) is False


def test_task_blocked_by_pending_dependency():
    dep = _make_task("dep1", status="pending")
    task = _make_task("t1", status="pending", depends=["dep1"])
    lookup = build_task_lookup([dep, task])
    assert is_task_ready(task, lookup) is False
    assert is_task_blocked(task, lookup) is True


def test_task_ready_when_dependency_is_completed():
    dep = _make_task("dep1", status="completed")
    task = _make_task("t1", status="pending", depends=["dep1"])
    lookup = build_task_lookup([dep, task])
    assert is_task_ready(task, lookup) is True
    assert is_task_blocked(task, lookup) is False


def test_unique_eight_character_prefix_resolves_dependency():
    dep = _make_task("12345678-completed", status="completed")
    task = _make_task("consumer", status="pending", depends=["12345678"])
    lookup = build_task_lookup([dep, task])

    assert lookup["12345678"] is dep
    assert is_task_ready(task, lookup) is True


def test_ambiguous_eight_character_prefix_does_not_resolve_dependency():
    dep1 = _make_task("12345678-first", status="completed")
    dep2 = _make_task("12345678-second", status="completed")
    task = _make_task("consumer", status="pending", depends=["12345678"])
    lookup = build_task_lookup([dep1, dep2, task])

    assert "12345678" not in lookup
    assert is_task_ready(task, lookup) is False
    assert is_task_blocked(task, lookup) is True


def test_task_blocked_by_missing_dependency():
    task = _make_task("t1", status="pending", depends=["non-existent-id"])
    lookup = build_task_lookup([task])
    assert is_task_ready(task, lookup) is False
    assert is_task_blocked(task, lookup) is True


def test_task_with_mixed_dependencies():
    dep1 = _make_task("dep1", status="completed")
    dep2 = _make_task("dep2", status="in-progress")
    task = _make_task("t1", status="pending", depends=["dep1", "dep2"])
    lookup = build_task_lookup([dep1, dep2, task])
    assert is_task_ready(task, lookup) is False
    assert is_task_blocked(task, lookup) is True


def test_filter_ready_and_blocked_lists():
    t_free = _make_task("free", status="pending")
    t_dep = _make_task("dep", status="pending")
    t_blocked = _make_task("blocked", status="pending", depends=["dep"])
    t_done = _make_task("done", status="completed")

    all_tasks = [t_free, t_dep, t_blocked, t_done]
    ready = filter_ready_tasks(all_tasks, all_tasks)
    blocked = filter_blocked_tasks(all_tasks, all_tasks)

    assert [t.id for t in ready] == ["free", "dep"]
    assert [t.id for t in blocked] == ["blocked"]
