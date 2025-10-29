"""Task model with YAML frontmatter support."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml
from dateutil import parser as date_parser


@dataclass
class Task:
    """Represents a task with YAML frontmatter and markdown body.

    Attributes:
        id: Unique task identifier
        title: Task title
        status: Task status (pending, in-progress, completed, cancelled)
        priority: Task priority (H=High, M=Medium, L=Low)
        project: Project name this task belongs to
        assignees: List of GitHub user handles (e.g., ['@user1', '@user2'])
        tags: List of tags for categorization
        links: List of associated URLs (e.g., GitHub issues, PRs, emails, docs)
        due: Due date for the task
        created: Creation timestamp
        modified: Last modification timestamp
        depends: List of task IDs this task depends on
        parent: Parent task ID (for subtasks)
        description: Markdown body/description of the task
        repo: Repository name this task belongs to
    """

    id: str
    title: str
    status: str = "pending"
    priority: str = "M"
    project: Optional[str] = None
    assignees: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    due: Optional[datetime] = None
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    depends: list[str] = field(default_factory=list)
    parent: Optional[str] = None
    description: str = ""
    repo: Optional[str] = None

    VALID_STATUSES = {"pending", "in-progress", "completed", "cancelled"}
    VALID_PRIORITIES = {"H", "M", "L"}

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate that a string is a valid HTTP/HTTPS URL.

        Args:
            url: URL string to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    def __post_init__(self):
        """Validate task fields after initialization."""
        if self.status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid status: '{self.status}'. Must be one of: {', '.join(self.VALID_STATUSES)}\n"
                f"Example: --status pending"
            )
        if self.priority not in self.VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority: '{self.priority}'. Must be one of: {', '.join(self.VALID_PRIORITIES)}\n"
                f"Example: --priority H (for High), M (for Medium), or L (for Low)"
            )

        # Validate links are valid URLs
        for link in self.links:
            if not self.validate_url(link):
                raise ValueError(
                    f"Invalid URL in links: '{link}'\n"
                    f"URLs must start with http:// or https://\n"
                    f"Examples:\n"
                    f"  --links https://github.com/user/repo/issues/123\n"
                    f"  --links https://docs.example.com,https://mail.google.com/..."
                )

    @classmethod
    def from_markdown(cls, content: str, task_id: str, repo: Optional[str] = None) -> "Task":
        """Parse a markdown file with YAML frontmatter into a Task object.

        Args:
            content: Markdown content with YAML frontmatter
            task_id: Task ID
            repo: Repository name

        Returns:
            Task object

        Raises:
            ValueError: If frontmatter is missing or invalid
        """
        # Extract YAML frontmatter using regex
        frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            raise ValueError("Invalid task format: YAML frontmatter not found")

        frontmatter_str = match.group(1)
        description = match.group(2).strip()

        # Parse YAML frontmatter
        try:
            metadata = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter: {e}") from e

        # Parse dates
        due = None
        if "due" in metadata and metadata["due"]:
            if isinstance(metadata["due"], datetime):
                due = metadata["due"]
            else:
                due = date_parser.parse(str(metadata["due"]))

        created = metadata.get("created", datetime.now())
        if not isinstance(created, datetime):
            created = date_parser.parse(str(created))

        modified = metadata.get("modified", datetime.now())
        if not isinstance(modified, datetime):
            modified = date_parser.parse(str(modified))

        # Parse links (support both list and single string for backward compatibility)
        links_raw = metadata.get("links", [])
        if isinstance(links_raw, str):
            links = [links_raw]
        elif isinstance(links_raw, list):
            links = links_raw
        else:
            links = []

        return cls(
            id=task_id,
            title=metadata.get("title", ""),
            status=metadata.get("status", "pending"),
            priority=metadata.get("priority", "M"),
            project=metadata.get("project"),
            assignees=metadata.get("assignees", []),
            tags=metadata.get("tags", []),
            links=links,
            due=due,
            created=created,
            modified=modified,
            depends=metadata.get("depends", []),
            parent=metadata.get("parent"),
            description=description,
            repo=repo,
        )

    def to_markdown(self) -> str:
        """Convert Task object to markdown with YAML frontmatter.

        Returns:
            Markdown string with YAML frontmatter
        """
        # Prepare metadata dict
        metadata = {
            "uuid": self.id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
        }

        if self.project:
            metadata["project"] = self.project
        if self.assignees:
            metadata["assignees"] = self.assignees
        if self.tags:
            metadata["tags"] = self.tags
        if self.due:
            metadata["due"] = self.due.isoformat()
        if self.depends:
            metadata["depends"] = self.depends
        if self.parent:
            metadata["parent"] = self.parent
        if self.links:
            metadata["links"] = self.links

        metadata["created"] = self.created.isoformat()
        metadata["modified"] = self.modified.isoformat()

        # Generate YAML frontmatter
        frontmatter = yaml.dump(metadata, default_flow_style=False, sort_keys=False)

        # Combine frontmatter and description
        return f"---\n{frontmatter}---\n\n{self.description}"

    def save(self, base_path: Path, subfolder: str = "tasks") -> Path:
        """Save task to a markdown file.

        Args:
            base_path: Base directory containing tasks/ or done/ subdirectory
            subfolder: Subdirectory name ("tasks" or "done"), defaults to "tasks"

        Returns:
            Path to the saved task file
        """
        # Update modification time
        self.modified = datetime.now()

        # Ensure target directory exists
        target_dir = base_path / subfolder
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except (IOError, OSError) as e:
            raise IOError(f"Failed to create task directory: {e}") from e

        # Save task
        task_file = target_dir / f"task-{self.id}.md"
        try:
            task_file.write_text(self.to_markdown())
        except (IOError, OSError) as e:
            raise IOError(f"Failed to save task file: {e}") from e

        return task_file

    @classmethod
    def load(cls, task_file: Path, repo: Optional[str] = None) -> "Task":
        """Load task from a markdown file.

        Args:
            task_file: Path to task markdown file
            repo: Repository name

        Returns:
            Task object
        """
        content = task_file.read_text()

        # Extract task ID from filename (task-001.md -> 001)
        task_id = task_file.stem.replace("task-", "")

        return cls.from_markdown(content, task_id, repo)

    def is_subtask(self) -> bool:
        """Check if this task is a subtask (has a parent).

        Returns:
            True if task has a parent, False otherwise
        """
        return self.parent is not None

    def get_depth(self, all_tasks: Optional[list["Task"]] = None) -> int:
        """Calculate the nesting depth of this task in the hierarchy.

        Args:
            all_tasks: List of all tasks to traverse up the parent chain.
                      If None, only checks if task has a parent (depth 0 or 1)

        Returns:
            Depth level (0 = top-level task, 1 = direct subtask, 2+ = nested subtask)
        """
        if not self.parent:
            return 0

        if all_tasks is None:
            # Can't calculate full depth without all tasks, return 1 for any subtask
            return 1

        # Find parent task and recursively calculate depth
        depth = 1
        current_parent_id = self.parent

        # Prevent infinite loops with visited set
        visited = {self.id}

        while current_parent_id:
            if current_parent_id in visited:
                # Circular reference detected
                break
            visited.add(current_parent_id)

            parent_task = next((t for t in all_tasks if t.id == current_parent_id), None)
            if parent_task and parent_task.parent:
                depth += 1
                current_parent_id = parent_task.parent
            else:
                break

        return depth

    def __str__(self) -> str:
        """String representation of the task."""
        assignees_str = f" {', '.join(self.assignees)}" if self.assignees else ""
        project_str = f" [{self.project}]" if self.project else ""
        return f"[{self.id}] {self.title}{project_str}{assignees_str} ({self.status}, {self.priority})"
