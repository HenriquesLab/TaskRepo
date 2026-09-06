import json
from pathlib import Path
from tempfile import TemporaryDirectory

from click.testing import CliRunner

from taskrepo.cli.commands.list import list_tasks
from taskrepo.core.config import Config
from taskrepo.core.repository import Repository
from taskrepo.core.task import Task


def _build_dependency_fixture(tmpdir: str) -> Config:
    parent = Path(tmpdir) / "parent"
    parent.mkdir()
    repo_dir = parent / "tasks-work"
    repo_dir.mkdir()
    repo = Repository(repo_dir)

    # dep task (pending)
    t_dep = Task(
        id="11111111-1111-1111-1111-111111111111",
        title="Prerequisite task",
        status="pending",
        priority="H",
    )
    repo.save_task(t_dep)

    # blocked task (depends on dep)
    t_blocked = Task(
        id="22222222-2222-2222-2222-222222222222",
        title="Dependent task",
        status="pending",
        priority="M",
        depends=["11111111-1111-1111-1111-111111111111"],
    )
    repo.save_task(t_blocked)

    # standalone ready task
    t_standalone = Task(
        id="33333333-3333-3333-3333-333333333333",
        title="Standalone task",
        status="pending",
        priority="L",
    )
    repo.save_task(t_standalone)

    # completed task
    t_done = Task(
        id="44444444-4444-4444-4444-444444444444",
        title="Done task",
        status="completed",
        priority="M",
    )
    repo.save_task(t_done)

    config_path = Path(tmpdir) / "config.yaml"
    config = Config(config_path=config_path)
    config._data["parent_dir"] = str(parent)
    config.save()
    return config


def test_list_ready_filters_out_blocked_and_completed_tasks():
    with TemporaryDirectory() as tmpdir:
        config = _build_dependency_fixture(tmpdir)
        runner = CliRunner()
        result = runner.invoke(list_tasks, ["--ready", "--json"], obj={"config": config})

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        titles = [t["title"] for t in data]
        assert "Prerequisite task" in titles
        assert "Standalone task" in titles
        assert "Dependent task" not in titles
        assert "Done task" not in titles


def test_list_blocked_shows_only_blocked_tasks():
    with TemporaryDirectory() as tmpdir:
        config = _build_dependency_fixture(tmpdir)
        runner = CliRunner()
        result = runner.invoke(list_tasks, ["--blocked", "--json"], obj={"config": config})

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        titles = [t["title"] for t in data]
        assert titles == ["Dependent task"]


def test_list_ready_and_blocked_mutually_exclusive():
    with TemporaryDirectory() as tmpdir:
        config = _build_dependency_fixture(tmpdir)
        runner = CliRunner()
        result = runner.invoke(list_tasks, ["--ready", "--blocked"], obj={"config": config})

        assert result.exit_code != 0
        assert "mutually exclusive" in result.output.lower() or "error" in result.output.lower()
