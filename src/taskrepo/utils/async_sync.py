"""Async sync utilities for background synchronization in TUI."""

from pathlib import Path

from taskrepo.core.repository import Repository
from taskrepo.utils.conflict_detection import resolve_readme_conflicts
from taskrepo.utils.merge import detect_conflicts, smart_merge_tasks


def sync_repository_background(repository: Repository, strategy: str = "auto", config=None) -> tuple[bool, str, bool]:
    """Sync a repository in background without user interaction.

    This is a simplified, non-interactive version of the sync command
    designed for background sync in the TUI.

    Args:
        repository: Repository to sync
        strategy: Merge strategy ("auto", "local", "remote")
        config: TaskRepo configuration (required for README generation)

    Returns:
        Tuple of (success, error_message, has_conflicts)
        - success: True if sync completed successfully
        - error_message: Error description if failed
        - has_conflicts: True if conflicts were detected and couldn't be auto-merged
    """
    if not repository.git_repo:
        return (False, "Not a git repository", False)

    git_repo = repository.git_repo

    if not git_repo.remotes:
        return (False, "No remote configured", False)

    try:
        # Step 1: Commit local changes if any
        if git_repo.is_dirty(untracked_files=True):
            # Check for unexpected files (non-task files)
            # In background mode, we skip unexpected files instead of prompting
            from taskrepo.utils.file_validation import detect_unexpected_files

            unexpected = detect_unexpected_files(git_repo, repository.path)

            if unexpected:
                # Skip this repo in background mode (needs manual intervention)
                return (
                    False,
                    "Unexpected files detected - manual sync required",
                    False,
                )

            # Commit local changes
            git_repo.git.add(A=True)
            git_repo.index.commit("Auto-commit: TaskRepo sync")

        # Step 2: Detect conflicts before pulling
        conflicts = detect_conflicts(git_repo, repository.path)

        if conflicts:
            # Try to auto-merge all conflicts
            unresolved = []

            for conflict in conflicts:
                resolved_task = None

                # Apply resolution strategy
                if strategy == "local":
                    resolved_task = conflict.local_task
                elif strategy == "remote":
                    resolved_task = conflict.remote_task
                elif strategy == "auto":
                    # Try smart merge
                    if conflict.can_auto_merge:
                        resolved_task = smart_merge_tasks(
                            conflict.local_task, conflict.remote_task, conflict.conflicting_fields
                        )

                if resolved_task:
                    # Save resolved task
                    repository.save_task(resolved_task)
                    git_repo.git.add(str(conflict.file_path))
                else:
                    # Cannot auto-merge this conflict
                    unresolved.append(conflict)

            if unresolved:
                # Cannot resolve all conflicts in background mode
                return (
                    False,
                    f"{len(unresolved)} conflicts need manual resolution",
                    True,
                )

            # Commit resolved conflicts
            if len(conflicts) > 0:
                git_repo.index.commit(f"Merge: Resolved {len(conflicts)} task conflict(s)")

        # Step 3: Pull changes
        try:
            git_repo.git.pull("--rebase=false", "origin", git_repo.active_branch.name)
        except Exception as e:
            if "would be overwritten" in str(e) or "conflict" in str(e).lower():
                # Pull created conflicts that we can't auto-resolve
                return (False, "Pull created conflicts - manual sync required", True)
            else:
                # Other error (network, etc.)
                return (False, str(e), False)

        # Step 4: Check for conflict markers and resolve them
        if _has_conflict_markers(repository.path):
            resolved_files = _resolve_conflict_markers_simple(repository)

            if not resolved_files:
                # Couldn't resolve conflict markers
                return (
                    False,
                    "Conflict markers need manual resolution",
                    True,
                )

            # Stage and commit resolved files
            for file_path in resolved_files:
                git_repo.git.add(str(file_path))
            git_repo.index.commit(f"Auto-resolve: Fixed {len(resolved_files)} conflict marker(s)")

        # Step 4b: Resolve README conflicts (auto-generated files, safe to auto-resolve)
        resolved_readmes = resolve_readme_conflicts(repository.path, console=None)
        if resolved_readmes:
            # Stage resolved README files
            for file_path in resolved_readmes:
                git_repo.git.add(str(file_path.relative_to(repository.path)))
            # Commit if we actually resolved README conflicts
            git_repo.index.commit(f"Auto-resolve: Fixed {len(resolved_readmes)} README conflict(s)")

        # Step 5: Update README files (skip if no config provided)
        if config:
            repository.generate_readme(config)
            repository.generate_archive_readme(config)

            # Step 6: Commit README changes if any
            if git_repo.is_dirty():
                # Add README files that exist and are modified
                readme_path = repository.path / "README.md"
                archive_readme_path = repository.path / "tasks" / "archive" / "README.md"

                if readme_path.exists():
                    git_repo.git.add("README.md")
                if archive_readme_path.exists():
                    git_repo.git.add("tasks/archive/README.md")

                # Only commit if something was actually staged
                if git_repo.is_dirty(index=True, working_tree=False, untracked_files=False):
                    git_repo.index.commit("Auto-update: README with tasks and archive")

        # Step 7: Push changes
        try:
            git_repo.git.push("origin", git_repo.active_branch.name)
        except Exception as e:
            # Push failed (network, auth, etc.) but local sync succeeded
            return (False, f"Push failed: {str(e)}", False)

        return (True, "", False)

    except Exception as e:
        return (False, str(e), False)


def _has_conflict_markers(repo_path: Path) -> bool:
    """Check if any task files have git conflict markers.

    Args:
        repo_path: Path to repository

    Returns:
        True if conflict markers found
    """
    tasks_dir = repo_path / "tasks"
    if not tasks_dir.exists():
        return False

    for task_file in tasks_dir.glob("task-*.md"):
        try:
            content = task_file.read_text()
            if "<<<<<<<" in content or ">>>>>>>" in content or "=======" in content:
                return True
        except Exception:
            continue

    return False


def _resolve_conflict_markers_simple(repository: Repository) -> list[Path]:
    """Resolve git conflict markers using smart merge.

    This is a simplified version that uses auto-merge only (no user interaction).

    Args:
        repository: Repository instance

    Returns:
        List of resolved file paths
    """
    from taskrepo.core.task import Task

    resolved_files: list[Path] = []
    tasks_dir = repository.path / "tasks"

    if not tasks_dir.exists():
        return resolved_files

    for task_file in tasks_dir.glob("task-*.md"):
        try:
            content = task_file.read_text()

            # Check for conflict markers
            if "<<<<<<<" not in content:
                continue

            # Try two strategies:
            # 1. If conflict is within YAML frontmatter (simple field conflicts), use remote version
            # 2. If conflict is complete file sections, try to parse and merge

            lines = content.split("\n")

            # Check if conflict is within YAML frontmatter
            # This happens when only simple fields like 'modified' conflict
            in_frontmatter = False
            conflict_in_frontmatter = False

            for i, line in enumerate(lines):
                if i == 0 and line == "---":
                    in_frontmatter = True
                elif in_frontmatter and line == "---":
                    in_frontmatter = False
                elif in_frontmatter and line.startswith("<<<<<<<"):
                    conflict_in_frontmatter = True
                    break

            # Strategy 1: Simple frontmatter conflict resolution
            if conflict_in_frontmatter:
                result_lines: list[str] = []
                in_conflict = False
                in_local = False
                local_lines: list[str] = []
                remote_lines: list[str] = []

                for line in lines:
                    if line.startswith("<<<<<<<"):
                        in_conflict = True
                        in_local = True
                        local_lines = []
                        remote_lines = []
                    elif line.startswith("=======") and in_conflict:
                        in_local = False
                    elif line.startswith(">>>>>>>") and in_conflict:
                        in_conflict = False
                        # Use remote version for frontmatter conflicts
                        result_lines.extend(remote_lines)
                    elif in_conflict:
                        if in_local:
                            local_lines.append(line)
                        else:
                            remote_lines.append(line)
                    else:
                        result_lines.append(line)

                # Validate the result is parseable
                try:
                    task_id = task_file.stem.replace("task-", "")
                    Task.from_markdown("\n".join(result_lines), task_id)

                    # Write resolved content
                    task_file.write_text("\n".join(result_lines))
                    resolved_files.append(task_file)
                except Exception:
                    # Can't parse result - skip this file
                    continue

            # Strategy 2: Complete file section conflicts
            else:
                local_lines = []
                remote_lines = []
                result_lines = []
                in_conflict = False
                in_local = False

                for line in lines:
                    if line.startswith("<<<<<<<"):
                        in_conflict = True
                        in_local = True
                        local_lines = []
                        remote_lines = []
                    elif line.startswith("=======") and in_conflict:
                        in_local = False
                    elif line.startswith(">>>>>>>") and in_conflict:
                        in_conflict = False

                        # Try to parse both versions
                        local_content = "\n".join(local_lines)
                        remote_content = "\n".join(remote_lines)

                        try:
                            task_id = task_file.stem.replace("task-", "")
                            _local_task = Task.from_markdown(local_content, task_id)
                            _remote_task = Task.from_markdown(remote_content, task_id)

                            # Use remote version
                            result_lines.extend(remote_lines)
                        except Exception:
                            # Can't parse - skip this file
                            continue

                    elif in_conflict:
                        if in_local:
                            local_lines.append(line)
                        else:
                            remote_lines.append(line)
                    else:
                        result_lines.append(line)

                # Validate and write
                try:
                    task_id = task_file.stem.replace("task-", "")
                    Task.from_markdown("\n".join(result_lines), task_id)

                    task_file.write_text("\n".join(result_lines))
                    resolved_files.append(task_file)
                except Exception:
                    # Can't parse result - skip this file
                    continue

        except Exception:
            # Failed to resolve this file - continue with others
            continue

    return resolved_files
