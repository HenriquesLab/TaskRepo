"""Task model with YAML frontmatter support."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from dateutil import parser as date_parser


@dataclass
class Task:
    """Represents a task with YAML frontmatter and markdown body.

    Attributes:
        id: Unique task identifier
        title: Task title
        status: Task status (pending, in_progress, completed, cancelled)
        priority: Task priority (H=High, M=Medium, L=Low)
        project: Project name this task belongs to
        assignees: List of GitHub user handles (e.g., ['@user1', '@user2'])
        tags: List of tags for categorization
        due: Due date for the task
        created: Creation timestamp
        modified: Last modification timestamp
        depends: List of task IDs this task depends on
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
    due: Optional[datetime] = None
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    depends: list[str] = field(default_factory=list)
    description: str = ""
    repo: Optional[str] = None

    VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}
    VALID_PRIORITIES = {"H", "M", "L"}

    def __post_init__(self):
        """Validate task fields after initialization."""
        if self.status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {self.status}. Must be one of {self.VALID_STATUSES}")
        if self.priority not in self.VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {self.priority}. Must be one of {self.VALID_PRIORITIES}")

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

        return cls(
            id=task_id,
            title=metadata.get("title", ""),
            status=metadata.get("status", "pending"),
            priority=metadata.get("priority", "M"),
            project=metadata.get("project"),
            assignees=metadata.get("assignees", []),
            tags=metadata.get("tags", []),
            due=due,
            created=created,
            modified=modified,
            depends=metadata.get("depends", []),
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
            "id": self.id,
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

        metadata["created"] = self.created.isoformat()
        metadata["modified"] = self.modified.isoformat()

        # Generate YAML frontmatter
        frontmatter = yaml.dump(metadata, default_flow_style=False, sort_keys=False)

        # Combine frontmatter and description
        return f"---\n{frontmatter}---\n\n{self.description}"

    def save(self, base_path: Path) -> Path:
        """Save task to a markdown file.

        Args:
            base_path: Base directory containing tasks/ subdirectory

        Returns:
            Path to the saved task file
        """
        # Update modification time
        self.modified = datetime.now()

        # Ensure tasks directory exists
        tasks_dir = base_path / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)

        # Save task
        task_file = tasks_dir / f"task-{self.id}.md"
        task_file.write_text(self.to_markdown())

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

    def __str__(self) -> str:
        """String representation of the task."""
        assignees_str = f" @{', @'.join(self.assignees)}" if self.assignees else ""
        project_str = f" [{self.project}]" if self.project else ""
        return f"[{self.id}] {self.title}{project_str}{assignees_str} ({self.status}, {self.priority})"
